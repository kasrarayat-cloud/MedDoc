"""What is actually submitted to the transcription provider, and what may be said about it.

Six things are checked here, and they are the six that were unpredictable before normalisation existed:
the ordinary browser WebM path; the other supported inputs; an ambiguous multi-track input refused
before anything is paid for; the shapes earlier passes found awkward (a trailing tag, an edit list, a
malformed chunk); the submitted artifact measured exactly, with the charge ceiling and consent binding
unchanged around it; and cancellation, provider failure and duplicate-charge prevention.

⚠️ THE LOSSLESS CLAIM IS TESTED BY DECODING, not by comparing durations. A duration that survives a
remux says the container still declares the same length; it does not say the samples are the same. So
each format's source and its normalised output are both decoded to raw s16le and compared byte for
byte. That is the only form of the claim worth making.

All fixtures are synthetic tones built on the machine running the test. No provider request leaves the
test database: httpx.post is patched in every case that reaches it, and the cases that must NOT reach
it assert the call count is zero.
"""
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from core import media
from core.jobs import enqueue, reap_stray_submissions, run_one
from core.media import NotNormalised, normalise_submission, plan_normalisation, probe_submission
from core.models import AuditEvent, Job, Reservation, Usage, Wallet
from core.security import private_path
from core.tests.audio_fixtures import wav_bytes, wav_with_two_data_chunks
from core.tests.test_billing_boundary import BoundaryFixture, deepgram
from core.tests.test_billing_policy import STORAGES
from exercised import requires_distinct, requires_input

STANDARD_ENV = {'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.006', 'QUILLMD_DEEPGRAM_RATE_PER_SECOND': '',
                'QUILLMD_VOICE_MAX_COST': '0.20', 'QUILLMD_PROVIDER_DISCOUNT_RATE': '0',
                'DEEPGRAM_API_KEY': 'synthetic-placeholder-not-a-key'}
TRANSCRIPT = 'Synthetic transcript: patient reports a mild headache.'
SECONDS = 4
# ⚠️ A MEASURED LITERAL, NOT media.NORMALISE_TOLERANCE_SECONDS. The assertions below used the production constant as
# their own bound, so the postcondition the code guarantees was the postcondition the test checked and raising the
# constant loosened both together — a test that cannot detect the thing it is testing drifting. This is the largest
# deviation actually observed across 31 recordings in every accepted format at 0.3, 1, 5, 60 and 600 seconds
# (M4A, against the ceiling, at 0.3 s), with a little room above it. If a remux ever exceeds it, that is a finding
# about the remux, and it must not be answerable by editing the constant in the other file.
MEASURED_WORST_DEVIATION = Decimal('0.05')


def ffmpeg_missing():
    """⚠️ ABSENT IS A SKIP ON A DEVELOPER'S MACHINE AND A FAILURE IN CI, AND CONFLATING THOSE MADE THE WHOLE SUITE
    VACUOUS. Measured with ffmpeg removed from PATH: 32 of these 34 tests skip, the two survivors are pure-Python and
    make no claim about the submission path, and `verify-fresh.sh` exits 0. The entire proof of what reaches the
    provider rested on one unasserted line of workflow YAML — edit it, or run on a runner image that drops ffmpeg,
    and there is no red anywhere.

    So the tool being missing is a HOST CAPABILITY gap where a host may legitimately lack it, and a BROKEN PROMISE
    where the workflow installs it on purpose. requires_input is the right instrument for the second: it is an input
    this environment guaranteed and did not supply.
    """
    missing = [name for name in ('ffmpeg', 'ffprobe') if shutil.which(name) is None]
    if missing and os.getenv('CI'):
        requires_input(False, 'the media tools the workflow installs (%s), which CI guarantees and did not supply — '
                              'without them 32 of these tests skip and the suite still reports OK'
                              % ', '.join(missing))
    return bool(missing)


def build(argv):
    finished = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y'] + argv, capture_output=True, timeout=120)
    if finished.returncode != 0:
        raise AssertionError('fixture build failed: ' + (finished.stderr or b'').decode('utf-8', 'replace')[:300])


def decoded(path):
    """The raw samples a decoder produces, so 'lossless' can be asserted about audio and not about metadata."""
    finished = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-f', 's16le', '-'],
                              capture_output=True, timeout=120)
    if finished.returncode != 0:
        raise AssertionError('decode failed: ' + (finished.stderr or b'').decode('utf-8', 'replace')[:300])
    return finished.stdout


class MediaFixtures:
    """One tone, encoded into every accepted input, plus the shapes that used to be unpredictable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.skip_reason = ('Submission normalisation NOT EXERCISED: ffmpeg/ffprobe are not on PATH, so nothing here could '
                           'be built or measured. No claim is made about this path from this run.') if ffmpeg_missing() else ''
        if cls.skip_reason:
            return
        cls.media = Path(tempfile.mkdtemp(prefix='submission-fixtures-'))
        tone = 'sine=frequency=440:duration=%d:sample_rate=48000' % SECONDS
        build(['-f', 'lavfi', '-i', tone, '-c:a', 'pcm_s16le', str(cls.media / 'tone.wav')])
        source = str(cls.media / 'tone.wav')
        build(['-i', source, '-c:a', 'libopus', '-b:a', '24k', str(cls.media / 'tone.webm')])
        build(['-i', source, '-c:a', 'libmp3lame', '-b:a', '64k', str(cls.media / 'tone.mp3')])
        build(['-i', source, '-c:a', 'aac', '-b:a', '64k', str(cls.media / 'tone.m4a')])
        # Two audio tracks in one container: which one a decoder reaches is not decided by the file.
        build(['-i', source, '-i', source, '-map', '0:a', '-map', '1:a', '-c:a', 'libopus', '-b:a', '24k',
               str(cls.media / 'two-tracks.webm')])
        # A .webm carrying VORBIS rather than Opus: one track, a measurable length — so it prices, queues and
        # holds — and no lossless remux defined for it, so the refusal lands in the WORKER with a reservation
        # outstanding. That is the reachable shape `UNREADABLE` had no money evidence for.
        build(['-i', source, '-c:a', 'libvorbis', str(cls.media / 'vorbis.webm')])
        # An MP4 whose edit list delays the start — the shape that used to move a recording's start time.
        build(['-i', str(cls.media / 'tone.m4a'), '-c:a', 'copy', '-output_ts_offset', '1.5',
               str(cls.media / 'edited.m4a')])
        # A trailing ID3v1 tag followed by 4 KB of junk: bytes after the audio that are not audio.
        (cls.media / 'tagged.mp3').write_bytes((cls.media / 'tone.mp3').read_bytes() + b'TAG' + b'x' * 125 + b'\x00' * 4096)

        # Sixty-five audio tracks: past MAX_AUDIO_STREAMS, which is where the refusal used to disappear.
        silence = str(cls.media / 'silence.m4a')
        build(['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '2', '-c:a', 'aac', '-b:a', '16k', silence])
        many = ['-i', silence] * 65
        for index in range(65):
            many += ['-map', '%d:a' % index]
        build(many + ['-c:a', 'copy', str(cls.media / 'many-tracks.m4a')])
        # An MP3 at exactly the upload limit with no Xing header and no ID3 tag: the remux ADDS both and grows it.
        build(['-f', 'lavfi', '-i', 'sine=frequency=440:duration=983.00:sample_rate=44100', '-c:a', 'libmp3lame',
               '-b:a', '128k', '-write_xing', '0', '-id3v2_version', '0', str(cls.media / 'at-the-limit.mp3')])

    @classmethod
    def tearDownClass(cls):
        if not cls.skip_reason:
            shutil.rmtree(cls.media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        if self.skip_reason:
            self.skipTest(self.skip_reason)
        super().setUp()

    def normalise(self, name):
        source = self.media / name
        requires_input(source.is_file(), 'the %s fixture' % name)
        from core import audio
        bounds = audio.measure_bounds(source.read_bytes())
        upload = probe_submission(source, ceiling_seconds=bounds.measured)
        _, suffix = plan_normalisation(upload)
        destination = Path(tempfile.mkdtemp(prefix='normalised-')) / ('out' + suffix)
        self.addCleanup(shutil.rmtree, destination.parent, True)
        return source, destination, upload, normalise_submission(source, destination, upload,
                                                                 floor_seconds=bounds.confirmed,
                                                                 ceiling_seconds=bounds.measured)


class NormalisationIsLosslessAndBounded(MediaFixtures, SimpleTestCase):
    def test_every_accepted_input_remuxes_to_byte_identical_audio(self):
        """The browser WebM path first, then the other three. Identity is asserted on decoded samples."""
        for name in ('tone.webm', 'tone.wav', 'tone.mp3', 'tone.m4a'):
            with self.subTest(name=name):
                source, destination, upload, produced = self.normalise(name)
                self.assertEqual(produced.audio_streams, 1)
                self.assertFalse(produced.ambiguous, produced.reasons)
                self.assertEqual(decoded(source), decoded(destination),
                                 '%s: the remux changed the audio a decoder produces' % name)
                self.assertLess(abs(produced.selected_seconds - upload.selected_seconds), MEASURED_WORST_DEVIATION)

    def test_a_trailing_tag_and_its_junk_are_removed_and_the_audio_is_not(self):
        source, destination, _, produced = self.normalise('tagged.mp3')
        self.assertLess(destination.stat().st_size, source.stat().st_size)
        # ⚠️ TWO OVER-STRONG CLAIMS WERE TRIED HERE FIRST, AND MEASURING THEM IS WHY THE COMMENT IS LONG.
        # Comparing the output against tone.mp3 itself failed correctly: the remux strips the encoder tag that file
        # carries, so they differ by 33 bytes of metadata. Comparing it byte-for-byte against a remux of tone.mp3 failed
        # too, by FOUR bytes — the muxer's seek table and the encoder delay/padding field, not audio.
        # What was actually measured: both remuxes are 32,468 bytes and both declare 4.032 s; the clean one decodes to
        # exactly 384,000 bytes of PCM and the tagged one to 384,862, and the first is a STRICT PREFIX of the second.
        # So the junk costs 431 samples — 9 ms — of trailing encoder padding that goes untrimmed, and not one sample
        # differs. That is the honest claim, and it is asserted below rather than the tidier one that is false.
        _, clean, _, _ = self.normalise('tone.mp3')
        self.assertEqual(destination.stat().st_size, clean.stat().st_size)
        self.assertEqual(decoded(source), decoded(destination), 'the remux changed the audio of its own source')
        tagged_pcm, clean_pcm = decoded(destination), decoded(clean)
        self.assertTrue(tagged_pcm.startswith(clean_pcm), 'the junk changed samples, not just trailing padding')
        self.assertLess(len(tagged_pcm) - len(clean_pcm), 48000 * 2 * 0.05, 'more than 50 ms of padding survived')
        self.assertGreater(produced.selected_seconds, Decimal(SECONDS) - MEASURED_WORST_DEVIATION)

    def test_an_edit_list_start_offset_is_flattened_and_the_audio_is_not_moved(self):
        before = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=start_time',
                                 '-of', 'csv=p=0', str(self.media / 'edited.m4a')], capture_output=True, timeout=60)
        offset = Decimal((before.stdout or b'0').decode().strip() or '0')
        requires_input(offset > Decimal('0.5'), 'an MP4 fixture whose edit list actually offsets the start')
        source, destination, _, produced = self.normalise('edited.m4a')
        after = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=start_time',
                                '-of', 'csv=p=0', str(destination)], capture_output=True, timeout=60)
        self.assertEqual(Decimal((after.stdout or b'0').decode().strip() or '0'), Decimal(0))
        self.assertEqual(decoded(source), decoded(destination))

    def test_more_than_one_audio_track_is_refused_and_no_output_is_produced(self):
        source = self.media / 'two-tracks.webm'
        upload = probe_submission(source)
        self.assertEqual(upload.audio_streams, 2)
        with self.assertRaises(NotNormalised):
            plan_normalisation(upload)

    def test_a_codec_with_no_lossless_remux_is_refused_rather_than_re_encoded(self):
        """The alternative — transcoding to something smaller — would discard a doctor's audio to make this path succeed."""
        upload = probe_submission(self.media / 'tone.wav')._replace(codec='some_future_codec')
        with self.assertRaises(NotNormalised) as refusal:
            plan_normalisation(upload)
        self.assertIn('some_future_codec', str(refusal.exception))

    def test_an_output_size_limit_kills_the_remux_and_leaves_nothing_to_submit(self):
        """A truncated payload is worse than no payload: it would be submitted, measured, and believed."""
        source = self.media / 'tone.wav'
        upload = probe_submission(source)
        destination = Path(tempfile.mkdtemp(prefix='bounded-')) / 'out.wav'
        self.addCleanup(shutil.rmtree, destination.parent, True)
        with patch.object(media, 'NORMALISE_MAX_OUTPUT_BYTES', 4096):
            with self.assertRaises(NotNormalised):
                normalise_submission(source, destination, upload, floor_seconds=Decimal(SECONDS))
        self.assertFalse(destination.exists(), 'a partial remux was left where the caller would have submitted it')

    def test_a_timeout_kills_the_remux_and_leaves_nothing_to_submit(self):
        source = self.media / 'tone.wav'
        upload = probe_submission(source)
        destination = Path(tempfile.mkdtemp(prefix='timed-')) / 'out.wav'
        self.addCleanup(shutil.rmtree, destination.parent, True)
        with patch.object(media, 'NORMALISE_TIMEOUT_SECONDS', 0.001):
            with self.assertRaises(NotNormalised):
                normalise_submission(source, destination, upload)
        self.assertFalse(destination.exists())

    def test_an_unexpected_subprocess_failure_is_a_refusal_with_nothing_left_behind(self):
        """normalise_submission promises that nothing survives a failure, so it is proved where that promise is the
        only thing acting — called directly, with no caller-side guard behind it.

        ⚠️ This exists because the job-level version of this check CANNOT prove it. There, jobs.py's own guard produces
        the identical outcome whether this handler is present or not, so the check passed with it reverted. A handler
        whose absence is invisible is not a proven handler; it is a redundancy, and redundancy is proved one layer at
        a time or not at all. The realistic trigger is a preexec_fn that raises, which setrlimit does when a hard
        limit sits below the value asked for.
        """
        source = self.media / 'tone.wav'
        upload = probe_submission(source)
        destination = Path(tempfile.mkdtemp(prefix='unexpected-')) / 'out.wav'
        self.addCleanup(shutil.rmtree, destination.parent, True)
        destination.touch(mode=0o600)
        with patch('core.media.subprocess.run', side_effect=subprocess.SubprocessError('Exception occurred in preexec_fn.')):
            with self.assertRaises(NotNormalised) as refusal:
                normalise_submission(source, destination, upload)
        self.assertIn('could not be run', str(refusal.exception))
        self.assertFalse(destination.exists(), 'the destination survived a failure this function promises to clean up')

    def test_the_remux_deviation_does_not_grow_with_the_length_of_the_recording(self):
        """A FIXED tolerance is only sound if the deviation is fixed too, and that is a claim about the cause.

        Measured across 0.3 s, 1 s, 5 s, 60 s and 600 s in all four accepted formats, the deviation is IDENTICAL at
        every length: WebM +0.008 s against the floor, MP3 -0.024, M4A -0.021. It is per-file container framing, not
        drift that accumulates — so NORMALISE_TOLERANCE_SECONDS does not need to scale with duration, and a doctor's
        hour-long recording is no closer to a refusal than a three-second one. If that ever stops being true, a fixed
        tolerance becomes a length limit nobody wrote down, which is why it is asserted rather than assumed.

        Nothing in the 0.3 s - 600 s matrix was refused. Worst margins: 10x on the loss side, 36x on the gain side.
        """
        from core import audio
        deviations = {}
        for seconds in (1, 60):
            name = 'span-%d.webm' % seconds
            build(['-f', 'lavfi', '-i', 'sine=frequency=440:duration=%d:sample_rate=48000' % seconds,
                   '-c:a', 'libopus', '-b:a', '24k', str(self.media / name)])
            source = self.media / name
            bounds = audio.measure_bounds(source.read_bytes())
            upload = probe_submission(source, ceiling_seconds=bounds.measured)
            _, suffix = plan_normalisation(upload)
            destination = Path(tempfile.mkdtemp(prefix='span-')) / ('out' + suffix)
            self.addCleanup(shutil.rmtree, destination.parent, True)
            produced = normalise_submission(source, destination, upload,
                                            floor_seconds=bounds.confirmed, ceiling_seconds=bounds.measured)
            deviations[seconds] = produced.selected_seconds - bounds.confirmed
        requires_distinct(list(deviations), 'two recordings of different lengths to compare', minimum=2)
        short, long = deviations[1], deviations[60]
        self.assertLess(abs(long - short), Decimal('0.002'),
                        'the deviation grew with duration (%s at 1 s, %s at 60 s), so a fixed tolerance is a length '
                        'limit nobody declared' % (short, long))
        self.assertLess(abs(long), MEASURED_WORST_DEVIATION,
                        'the measured deviation is no longer comfortably inside what was measured')
        self.assertLess(MEASURED_WORST_DEVIATION, media.NORMALISE_TOLERANCE_SECONDS,
                        'the production tolerance has been tightened past what real recordings actually deviate by, '
                        'which would refuse legitimate audio rather than merely fail to catch loss')

    def test_every_refusal_removes_the_destination_including_the_one_taken_before_any_work(self):
        """The cleanup is one owner now, so the arm that never had one is the arm worth proving.

        plan_normalisation refuses before ffmpeg is even located, and the caller has already created the file by then.
        Nine separate unlinks covered eight of the nine exits; this is the ninth.
        """
        multi = probe_submission(self.media / 'two-tracks.webm')
        requires_input(multi.audio_streams > 1, 'a multi-track fixture that refuses before any remux work')
        destination = Path(tempfile.mkdtemp(prefix='refused-')) / 'out.webm'
        self.addCleanup(shutil.rmtree, destination.parent, True)
        destination.touch(mode=0o600)
        self.assertTrue(destination.exists())
        with self.assertRaises(NotNormalised):
            normalise_submission(self.media / 'two-tracks.webm', destination, multi)
        self.assertFalse(destination.exists(), 'the earliest refusal left the file the caller had created')

    def test_an_output_that_holds_less_audio_than_the_source_is_refused(self):
        """The loss check itself. Both sides are measured by the same instrument, so the comparison is exact."""
        source = self.media / 'tone.wav'
        upload = probe_submission(source)
        destination = Path(tempfile.mkdtemp(prefix='short-')) / 'out.wav'
        self.addCleanup(shutil.rmtree, destination.parent, True)
        real = media.probe_submission
        short = [None]

        def shrink(path, ceiling_seconds=None, timeout=None):
            described = real(path, ceiling_seconds=ceiling_seconds)
            if Path(path) == destination:
                short[0] = described._replace(selected_seconds=described.selected_seconds - Decimal(2))
                return short[0]
            return described

        with patch.object(media, 'probe_submission', shrink):
            with self.assertRaises(NotNormalised) as refusal:
                normalise_submission(source, destination, upload, floor_seconds=Decimal(SECONDS))
        requires_input(short[0] is not None, 'a measurement of the produced artifact to shorten')
        self.assertIn("source's certain", str(refusal.exception))
        self.assertFalse(destination.exists())

    def test_an_output_declaring_more_audio_than_the_source_could_hold_is_refused(self):
        """The other side of the same guard: our own muxer overstating a length is not a lucky gain."""
        source = self.media / 'tone.wav'
        upload = probe_submission(source)
        destination = Path(tempfile.mkdtemp(prefix='long-')) / 'out.wav'
        self.addCleanup(shutil.rmtree, destination.parent, True)
        real = media.probe_submission

        def inflate(path, ceiling_seconds=None, timeout=None):
            described = real(path, ceiling_seconds=ceiling_seconds)
            return described._replace(selected_seconds=described.selected_seconds + Decimal(30)) \
                if Path(path) == destination else described

        with patch.object(media, 'probe_submission', inflate):
            with self.assertRaises(NotNormalised) as refusal:
                normalise_submission(source, destination, upload, ceiling_seconds=Decimal(SECONDS))
        self.assertIn("source's utmost", str(refusal.exception))
        self.assertFalse(destination.exists())


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class AmbiguousInputIsRefusedBeforeAnythingIsPaidFor(MediaFixtures, BoundaryFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def upload(self, name, content_type, env=STANDARD_ENV):
        with patch.dict(os.environ, env):
            page = self.client.get(f'/encounters/{self.encounter.pk}/')
            return self.client.post(f'/encounters/{self.encounter.pk}/voice/', {
                'audio': SimpleUploadedFile(name, (self.media / name).read_bytes(), content_type=content_type),
                'consent': 'on', 'usage_quote': page.context['usage_quote']}, follow=True)

    def test_two_audio_tracks_create_no_job_no_hold_and_no_provider_request(self):
        with patch('core.jobs.httpx.post') as post:
            response = self.upload('two-tracks.webm', 'audio/webm')
        self.assertEqual(post.call_count, 0, 'a payload nobody could interpret reached the provider')
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 0)
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertEqual(Usage.objects.count(), 0)
        self.assertContains(response, 'separate audio tracks')
        # The refused upload is not kept either: an audio file nobody can interpret is not evidence of anything.
        self.assertEqual(sorted(private_path('audio').glob('*')) if private_path('audio').is_dir() else [], [])

    def test_one_audio_track_is_not_refused_by_the_same_check(self):
        """The positive control. A refusal that fires on everything would pass the test above and break the product."""
        with patch('core.jobs.httpx.post', return_value=deepgram(TRANSCRIPT, 'dg_single', duration=SECONDS)) as post:
            response = self.upload('tone.webm', 'audio/webm')
            self.assertTrue(response.redirect_chain, 'the accepted upload did not redirect to the encounter')
            job = Job.objects.get(encounter=self.encounter, kind='transcription')
            with patch.dict(os.environ, STANDARD_ENV):
                self.assertTrue(run_one())
        self.assertEqual(post.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class WhatWasSubmittedIsWhatWasMeasured(MediaFixtures, BoundaryFixture, TestCase):
    """The recorded description must describe the bytes that went out — checked against the bytes that went out."""

    def run_upload(self, name, suffix, duration=SECONDS, transcript=TRANSCRIPT):
        relative = f'uploads/submission-{name.replace(".", "-")}{suffix}'
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((self.media / name).read_bytes())
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post', return_value=deepgram(transcript, 'dg_' + name, duration=duration)) as post:
                self.assertTrue(run_one())
        job.refresh_from_db()
        return job, post

    def test_the_recorded_sha256_bytes_and_duration_are_those_of_the_posted_payload(self):
        for name, suffix in (('tone.webm', '.webm'), ('tone.wav', '.wav'), ('tone.mp3', '.mp3'), ('tone.m4a', '.m4a')):
            with self.subTest(name=name):
                job, post = self.run_upload(name, suffix)
                self.assertEqual(job.state, 'succeeded')
                sent = post.call_args.kwargs['content']
                usage = Usage.objects.get(job=job)
                self.assertEqual(usage.units['submission_source'], 'normalised', usage.units.get('normalisation_detail'))
                self.assertEqual(usage.units['submission_sha256'], hashlib.sha256(sent).hexdigest())
                self.assertEqual(usage.units['submission_bytes'], str(len(sent)))
                self.assertEqual(usage.units['upload_path'], job.input_path)
                # The duration is re-measured here from the posted bytes, not copied from the record being checked.
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                    handle.write(sent)
                    measured = probe_submission(handle.name)
                os.unlink(handle.name)
                self.assertEqual(usage.units['submitted_seconds'], str(measured.selected_seconds))
                self.assertEqual(usage.units['submission_status'], 'determined')

    def test_the_priced_ceiling_is_never_below_what_was_submitted(self):
        """The money invariant, stated over the artifact rather than over the upload."""
        for name, suffix in (('tone.webm', '.webm'), ('tone.wav', '.wav'), ('tone.mp3', '.mp3'), ('tone.m4a', '.m4a')):
            with self.subTest(name=name):
                job, _ = self.run_upload(name, suffix)
                usage = Usage.objects.get(job=job)
                # ⚠️ STATED WITH THE ROUNDING, BECAUSE THE BARE FORM IS FALSE AND THIS TEST ASSERTED IT. A copy-remuxed
                # WebM declares 4.028 s where the hand measurement of its source says 4.021 s — 7 ms of container
                # rounding, with decoded samples proven byte-identical above. No money moves on this number: the charge
                # is computed from the provider's reported duration and capped by charge_limit, which already carries a
                # 2% + 2 s margin. What the ceiling bounds is the AUDIO, not every container's declaration of it.
                ceiling, submitted = Decimal(job.config['recording_seconds']), Decimal(usage.units['submitted_seconds'])
                self.assertGreaterEqual(ceiling + MEASURED_WORST_DEVIATION, submitted)
                self.assertLessEqual(usage.charged_cost, Decimal(job.config['charge_limit']))

    def test_a_provider_that_processed_less_than_was_submitted_says_so_in_the_transcript(self):
        job, _ = self.run_upload('tone.webm', '.webm', duration=1)
        stored = private_path(job.result_path).read_text()
        self.assertIn('Transcription incomplete', stored)

    def test_matching_durations_add_no_claim_of_completeness(self):
        job, _ = self.run_upload('tone.mp3', '.mp3')
        stored = private_path(job.result_path).read_text()
        self.assertNotIn('Transcription incomplete', stored)
        self.assertNotIn('coverage UNKNOWN', stored)
        self.assertNotIn('complete', stored.lower().replace('incomplete', ''))

    def test_the_artifact_exists_while_the_request_is_in_flight_and_is_gone_afterwards(self):
        seen = {}

        def capture(*args, **kwargs):
            live = sorted(private_path('submissions').glob('*')) if private_path('submissions').is_dir() else []
            seen['during'] = [(p.name, oct(p.stat().st_mode & 0o777)) for p in live]
            return deepgram(TRANSCRIPT, 'dg_transient', duration=SECONDS)

        relative = 'uploads/transient.webm'
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((self.media / 'tone.webm').read_bytes())
        with patch.dict(os.environ, STANDARD_ENV):
            enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post', side_effect=capture):
                self.assertTrue(run_one())
        requires_input('during' in seen, 'a provider call to observe the artifact from')
        self.assertEqual(len(seen['during']), 1, seen['during'])
        self.assertEqual(seen['during'][0][1], '0o600', 'the transient artifact was not private')
        self.assertEqual(sorted(private_path('submissions').glob('*')), [], 'the artifact outlived its request')

    def test_a_provider_failure_also_leaves_no_artifact_behind(self):
        relative = 'uploads/failing.webm'
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((self.media / 'tone.webm').read_bytes())
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post', side_effect=RuntimeError('provider refused the connection')):
                self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertIn(job.state, ('failed', 'reconciliation'))
        self.assertEqual(sorted(private_path('submissions').glob('*')), [], 'a failed request left its payload on disk')


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class StrayArtifactsAreReapedAndNothingElseIs(BoundaryFixture, TestCase):
    def write(self, name, age_seconds):
        path = private_path('submissions/' + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(wav_bytes(seconds=1, tag=name))
        stamp = path.stat().st_mtime - age_seconds
        os.utime(path, (stamp, stamp))
        return path

    def test_only_an_old_correctly_named_artifact_is_removed(self):
        old = self.write('a' * 48 + '.wav', 7200)
        fresh = self.write('b' * 48 + '.wav', 0)
        foreign = self.write('not-a-submission-name.wav', 7200)
        self.assertEqual(reap_stray_submissions(), 1)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists(), 'an artifact from a request that may still be in flight was deleted')
        self.assertTrue(foreign.exists(), 'the reaper deleted a file it does not own')


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ConsentAndDeduplicationAreUnchanged(MediaFixtures, BoundaryFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def post_recording(self, consent, name='tone.webm', content_type='audio/webm'):
        with patch.dict(os.environ, STANDARD_ENV):
            page = self.client.get(f'/encounters/{self.encounter.pk}/')
            body = {'audio': SimpleUploadedFile(name, (self.media / name).read_bytes(), content_type=content_type),
                    'usage_quote': page.context['usage_quote']}
            if consent:
                body['consent'] = 'on'
            return self.client.post(f'/encounters/{self.encounter.pk}/voice/', body, follow=True)

    def test_without_consent_nothing_is_normalised_queued_or_sent(self):
        with patch('core.jobs.httpx.post') as post:
            response = self.post_recording(consent=False)
        self.assertEqual(post.call_count, 0)
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 0)
        self.assertContains(response, 'confirm provider processing')

    def test_a_cancelled_request_normalises_nothing_sends_nothing_and_charges_nothing(self):
        """Normalisation happens inside the provider request, so a request that never happens must leave no trace of one."""
        from core.jobs import cancel
        relative = 'uploads/cancelled.webm'
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((self.media / 'tone.webm').read_bytes())
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            self.assertEqual(Reservation.objects.filter(job=job).count(), 1)
            with patch('core.jobs.httpx.post') as post:
                cancel(job, self.user)
                self.assertFalse(run_one(), 'a cancelled job was picked up')
        job.refresh_from_db()
        self.assertEqual(job.state, 'cancelled')
        self.assertEqual(post.call_count, 0)
        self.assertEqual(Usage.objects.filter(job=job).count(), 0)
        self.assertEqual(sorted(private_path('submissions').glob('*')) if private_path('submissions').is_dir() else [], [])
        self.assertTrue(path.is_file(), 'the doctor\'s upload was destroyed by a cancellation')

    def test_the_same_recording_twice_is_one_job_and_one_charge(self):
        relative = 'uploads/duplicate.webm'
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((self.media / 'tone.webm').read_bytes())
        with patch.dict(os.environ, STANDARD_ENV):
            first = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post', return_value=deepgram(TRANSCRIPT, 'dg_dup', duration=SECONDS)) as post:
                self.assertTrue(run_one())
            second = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(Usage.objects.filter(job=first, simulated=False).count(), 1)


class AMalformedRecordingIsRefusedBeforeNormalisationIsReached(SimpleTestCase):
    """A declared size the bytes cannot support is refused where it always was — before any charge or remux."""

    def test_a_wav_whose_declared_size_is_impossible_is_still_measured_from_its_samples(self):
        """An oversized declaration does not become a longer recording: the length comes from the bytes present.

        This started out asserting a refusal, on the strength of an earlier fixture that WAS refused. It was the fixture
        that was malformed, not the shape — it patched offset 40 as if every WAV had a 44-byte header, and this one does
        not. The header is located properly here, and the real behaviour is the safer of the two: the declared size is
        ignored and the samples are counted."""
        import struct
        from core import audio
        raw = wav_bytes(seconds=2, tag='oversized')
        at = raw.index(b'data')
        requires_input(at > 12, 'a WAV fixture with a locatable data chunk header')
        inflated = raw[:at + 4] + struct.pack('<I', 0xFFFFFF00) + raw[at + 8:]
        honest, lying = audio.measure_bounds(raw), audio.measure_bounds(inflated)
        self.assertEqual(honest.measured, lying.measured)
        self.assertAlmostEqual(float(lying.measured), 2.0, places=2)

    def test_a_split_wav_prices_the_whole_file_and_never_promises_the_hidden_part_was_sent(self):
        """KNOWN AND UNCHANGED: a decoder reaches one data chunk. The ceiling covers both, so the charge is safe, and no
        statement of completeness is made about the part no decoder reaches. Normalisation does not create this and does
        not resolve it — it is recorded here so the next reader does not mistake the silence for a guarantee."""
        if ffmpeg_missing():
            self.skipTest('Split-WAV submission NOT EXERCISED: ffprobe is not on PATH.')
        from core import audio
        raw = wav_with_two_data_chunks(9, 1)
        bounds = audio.measure_bounds(raw)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as handle:
            handle.write(raw)
            described = probe_submission(handle.name, ceiling_seconds=bounds.measured)
        os.unlink(handle.name)
        self.assertEqual(described.audio_streams, 1)
        self.assertAlmostEqual(float(described.selected_seconds), 1.0, places=1)
        self.assertAlmostEqual(float(bounds.measured), 10.0, places=1)
        self.assertGreaterEqual(bounds.measured, described.selected_seconds)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class WhatTheRefutationPassFound(MediaFixtures, BoundaryFixture, TestCase):
    """Six defects the adversarial pass demonstrated, each pinned by the input that demonstrated it.

    Every one of them failed in the same direction — refusing, charging for, or silently narrowing a recording a doctor
    had made correctly — and none was reachable from the happy path these tests otherwise walk.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def enqueue_file(self, name, suffix, relative=None):
        relative = relative or f'uploads/refutation-{name.replace(".", "-")}{suffix}'
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((self.media / name).read_bytes())
        return relative

    def test_sixty_five_audio_tracks_are_refused_exactly_as_two_are(self):
        """The refusal was a positive test on a string the failure path set to empty, so it vanished above 64 tracks.

        Measured before the fix: a job, a $0.06 hold, one provider request and a $0.0525 charge, for a payload holding
        65 recordings of which the provider silently decoded one.
        """
        relative = self.enqueue_file('many-tracks.m4a', '.m4a')
        streams = probe_submission(private_path(relative)).audio_streams
        requires_input(streams > 64, 'a fixture with more audio tracks than the probe reports individually')
        with patch.dict(os.environ, STANDARD_ENV), patch('core.jobs.httpx.post') as post:
            with self.assertRaises(ValidationError) as refusal:
                enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
        self.assertIn('separate audio tracks', str(refusal.exception))
        self.assertEqual(post.call_count, 0)
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 0)
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertEqual(Usage.objects.count(), 0)

    def test_a_payload_with_no_audio_track_is_refused_before_any_charge(self):
        """⚠️ EXERCISED BY PATCHING THE PROBE, AND THE REASON MATTERS. core/audio.py measures a recording by hand
        before this guard is reached and refuses anything it cannot find audio structure in, so no real file that gets
        this far has been shown to probe as zero audio streams. The guard exists for a DISAGREEMENT between the two
        instruments — our parser finding audio where ffprobe finds no stream — and refusing is the safe answer to
        that. What this proves is that the branch works and refuses before any hold; it does not prove the branch is
        reachable from a real upload, and that limitation is stated rather than papered over with a fixture that
        merely satisfies it.
        """
        relative = self.enqueue_file('tone.webm', '.webm', 'uploads/no-audio.webm')
        real = probe_submission

        def no_streams(path, **kwargs):
            return real(path, **kwargs)._replace(audio_streams=0, selected_seconds=None, ambiguous=True,
                                                 reasons=['ffprobe found no audio stream in the submitted payload'])

        with patch.dict(os.environ, STANDARD_ENV), patch('core.jobs.probe_submission', no_streams):
            with patch('core.jobs.httpx.post') as post:
                with self.assertRaises(ValidationError) as refusal:
                    enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
        self.assertIn('No audio track', str(refusal.exception))
        self.assertEqual(post.call_count, 0)
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 0)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_a_host_without_ffprobe_is_reported_as_the_host_not_the_recording(self):
        """⚠️ HALF THE TOOLCHAIN MISSING USED TO BLAME THE DOCTOR'S FILE, AND ONLY HALF THE TIME.

        ffmpeg absent gave `unavailable` / retryable — correct. ffprobe absent gave `unreadable` / NOT retryable, and
        told the doctor to re-export a recording that was fine, because the caller flattened every
        SubmissionUnprobeable to UNREADABLE. Four unrelated causes arrive that way and only one is about the file.
        On a host where ffprobe is missing, EVERY recording is refused and every doctor is pointed at their own
        upload — while `kind`/`retryable`, the one structured signal an operator has, points away from the host.
        """
        real_which = shutil.which
        for tool in ('ffmpeg', 'ffprobe'):
            with self.subTest(missing=tool):
                relative = self.enqueue_file('tone.webm', '.webm', 'uploads/no-%s.webm' % tool)
                with patch.dict(os.environ, STANDARD_ENV):
                    job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
                    with patch('core.media.shutil.which',
                               lambda name, tool=tool: None if name == tool else real_which(name)):
                        with patch('core.jobs.httpx.post') as post:
                            self.assertTrue(run_one())
                # Both halves of the same toolchain, the same host fault, the same answer.
                self.assert_stopped_cleanly(job, post, media.UNAVAILABLE, retryable=True)

    def test_a_refusal_survives_a_database_that_cannot_record_it(self):
        """⚠️ THE AUDIT WRITE USED TO BE ABLE TO STRAND THE MONEY IT EXISTS TO RETURN.

        refuse() added a SELECT and an INSERT to every failure path — paths that previously touched no database — and
        that INSERT lands right after up to 45 s of subprocess work, which is when the worker's single long-held
        connection is most likely to be stale. When it raised, the escaping exception was no longer a
        NoProviderRequest, so run_one classified the job `reconciliation` rather than `unsent`: the hold was never
        released, mark_stale could not help, `request_key` was never freed so the encounter refused every later
        recording, and audit_billing's hold policy only inspects succeeded/failed/cancelled jobs — so
        `all_checks_pass` stayed True over stranded funds.
        """
        from core import jobs as jobs_module
        relative = self.enqueue_file('tone.webm', '.webm', 'uploads/audit-down.webm')
        real_audit = jobs_module.audit

        def audit_fails_only_for_the_refusal(actor, action, target='', **details):
            if action == 'voice.submission_refused':
                raise RuntimeError('server closed the connection unexpectedly')
            return real_audit(actor, action, target, **details)

        real_which = shutil.which
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch.object(jobs_module, 'audit', audit_fails_only_for_the_refusal), \
                 patch('core.media.shutil.which', lambda name: None if name == 'ffmpeg' else real_which(name)):
                with patch('core.jobs.httpx.post') as post:
                    self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(post.call_count, 0)
        # The refusal still happened, which is the whole point: the money comes back even when the record does not.
        self.assertEqual(job.state, 'failed', 'a failed audit write pushed the job into reconciliation')
        self.assertIn('nothing was charged and the held funds were released', job.error)
        self.assertEqual([r.state for r in Reservation.objects.filter(job=job)], ['released'])
        self.assertEqual(Usage.objects.filter(job=job).count(), 0)
        # The evidence row is the thing that was lost, and losing it is the accepted cost.
        self.assertEqual(AuditEvent.objects.filter(action='voice.submission_refused', target=str(job.pk)).count(), 0)

    def test_a_recording_whose_prepared_payload_is_too_large_stops_and_says_which_is_too_large(self):
        """The muxer adds an ID3v2 header and a Xing frame to a tagless MP3, so the artifact crosses the limit the
        upload sat exactly on. Raising there told the doctor 'Recording too large.' about a recording that was inside
        the limit and had transcribed fine before — deterministically, so re-uploading never helped."""
        """The muxer adds an ID3v2 header and a Xing frame a tagless MP3 lacks, so the artifact crosses a limit the
        upload sat exactly on. This used to fall back to the original; it now stops.

        ⚠️ AND THE MESSAGE IS THE POINT. The pre-normalisation code said 'Recording too large.' about a recording that
        was INSIDE the limit, which is false and sends the doctor looking for a problem in the wrong place. What is
        too large is the prepared payload, and the remedy — a shorter segment — is the same either way, so the
        sentence says that instead."""
        relative = self.enqueue_file('at-the-limit.mp3', '.mp3')
        original = private_path(relative).read_bytes()
        requires_input(len(original) == 15 * 1024 * 1024, 'an upload sitting exactly on the submission limit')
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post') as post:
                self.assertTrue(run_one())
        self.assert_stopped_cleanly(job, post, media.TOO_LARGE, retryable=False)
        self.assertNotIn('Recording too large', job.error,
                         'the upload was inside the limit; only the prepared payload was not')

    def test_a_failing_audit_write_leaves_no_artifact_on_the_encrypted_volume(self):
        """The artifact was created, then the audit row was written outside any guard that could clean it up.

        This is not an exotic fault: the worker holds one database connection across up to 25 s of subprocess work, so
        a stale-connection error lands at exactly this INSERT.
        """
        relative = self.enqueue_file('tone.webm', '.webm', 'uploads/audit-fails.webm')
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            from core import jobs as jobs_module
            with patch.object(jobs_module, 'audit', side_effect=RuntimeError('server closed the connection')):
                with self.assertRaises(RuntimeError):
                    jobs_module.prepare_submission(job)
        self.assertEqual(sorted(private_path('submissions').glob('*')), [],
                         'the artifact survived a failure between writing it and handing it back')


    def assert_stopped_cleanly(self, job, post, kind, retryable):
        """Nothing sent, nothing charged, the hold released EXACTLY once, and the doctor told something actionable."""
        from core.media import REFUSAL_TEXT
        job.refresh_from_db()
        self.assertEqual(post.call_count, 0, 'the provider was contacted despite a processing failure')
        self.assertEqual(job.state, 'failed', job.error)
        self.assertEqual(Usage.objects.filter(job=job).count(), 0, 'a failure that never reached the provider was charged')
        self.assertIn(REFUSAL_TEXT[kind], job.error)
        self.assertIn('nothing was charged and the held funds were released', job.error)
        if retryable:
            self.assertIn('Try again', job.error)
        else:
            self.assertNotIn('Try again', job.error,
                             'a cause that re-sending the same bytes cannot fix must not invite a retry')
        # EXACTLY ONCE: every reservation ended released, and there is one release row per reservation — not two.
        reservations = Reservation.objects.filter(job=job)
        self.assertTrue(reservations.exists(), 'the fixture never held anything, so releasing it proves nothing')
        self.assertEqual([r.state for r in reservations], ['released'] * reservations.count())
        releases = AuditEvent.objects.filter(action='usage.release', target=str(job.pk)).count()
        self.assertEqual(releases, reservations.count(),
                         'the hold was released %d times for %d reservations' % (releases, reservations.count()))
        # And the wallet is back where it started, which is what a double release would break.
        for wallet in Wallet.objects.all():
            self.assertGreaterEqual(wallet.reserved, Decimal(0), 'a wallet was decremented more than it was incremented')
        # The refusal is on the record, with its cause, and without a storage path.
        refusals = AuditEvent.objects.filter(action='voice.submission_refused', target=str(job.pk))
        self.assertEqual(refusals.count(), 1)
        details = refusals.first().details
        self.assertEqual(details['kind'], kind)
        self.assertEqual(details['retryable'], retryable)
        self.assertNotIn('/', details['detail'], 'a filesystem path reached the audit row')
        self.assertEqual(sorted(private_path('submissions').glob('*')), [], 'a failed preparation left its artifact')

    def test_a_host_without_ffmpeg_stops_and_sends_nothing(self):
        """⚠️ THIS TEST ASSERTED THE OPPOSITE AND THE OPPOSITE WAS THE DEFECT. It required the original upload to be
        submitted when ffmpeg was missing, on the reasoning that a fallback is never worse than the behaviour before
        normalisation existed. It is worse: the provider decides for itself what to decode, the doctor is charged for
        the result, and the only trace that the processing step stopped running is a string on a usage row."""
        relative = self.enqueue_file('tone.webm', '.webm', 'uploads/no-ffmpeg.webm')
        real_which = shutil.which
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.media.shutil.which', lambda name: None if name == 'ffmpeg' else real_which(name)):
                with patch('core.jobs.httpx.post') as post:
                    self.assertTrue(run_one())
        self.assert_stopped_cleanly(job, post, media.UNAVAILABLE, retryable=True)

    def test_a_remux_that_raises_something_unexpected_stops_and_releases_the_hold(self):
        """A preexec_fn that raises surfaces as a bare SubprocessError. Uncaught, it escaped media.py's handler AND
        jobs.py's, left a stray artifact, and put the job in reconciliation with the doctor's money held — for what
        should have been a silent fallback to the original.

        ⚠️ BOTH LAYERS ARE EXERCISED SEPARATELY, because the first version of this test only exercised one. It patched
        subprocess.run, which media.py now catches, so reverting jobs.py's handler left the test passing — a check that
        could not fail for the guard it named. Each subTest below raises at the layer whose handler it is proving.
        """
        # ⚠️ A DIFFERENT RECORDING PER LAYER, because two byte-identical uploads are ONE request by design: the
        # request_key is the upload's sha256, so the second enqueue returned the first (already finished) job and
        # run_one had nothing queued. That is duplicate-charge prevention working, and it silently emptied a subTest.
        # ⚠️ AND THE FIRST LAYER MUST FAIL ONLY THE REMUX. Failing every subprocess.run in media.py breaks the source
        # probe first, so normalise_submission is never reached and media.py's own handler is never exercised — the
        # test passed with that handler reverted. This lets ffprobe through and fails ffmpeg alone.
        real_run = subprocess.run

        def only_the_remux_fails(argv, **kwargs):
            if str(argv[0]).endswith('ffmpeg'):
                raise subprocess.SubprocessError('Exception occurred in preexec_fn.')
            return real_run(argv, **kwargs)

        layers = ((only_the_remux_fails, 'core.media.subprocess.run', 'the remux subprocess', 'tone.webm', '.webm'),
                  (subprocess.SubprocessError('Exception occurred in preexec_fn.'), 'core.jobs.normalise_submission',
                   'the remux call itself', 'tone.m4a', '.m4a'))
        for failure, target, where, fixture, suffix in layers:
            with self.subTest(layer=where):
                relative = self.enqueue_file(fixture, suffix, 'uploads/subprocess-error-%s%s' % (len(where), suffix))
                original = private_path(relative).read_bytes()
                with patch.dict(os.environ, STANDARD_ENV):
                    job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
                    with patch(target, side_effect=failure):
                        with patch('core.jobs.httpx.post') as post:
                            self.assertTrue(run_one())
                # An unexpected exception class is exactly where least is known about the artifact, so it is the last
                # case that should ever be submitted anyway. Both layers stop, and both release the hold once.
                self.assert_stopped_cleanly(job, post, media.UNAVAILABLE, retryable=True)

    def test_overrunning_the_preparation_budget_stops_rather_than_submitting_anything(self):
        """The unit SIGKILLs the whole cgroup 150 s after SIGTERM. Summing the sub-step ceilings reached 250 s, so a
        routine restart could kill a worker mid-remux. Exceeding the budget must cost normalisation, never the job."""
        relative = self.enqueue_file('tone.webm', '.webm', 'uploads/budget.webm')
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch.object(media, 'SUBMISSION_BUDGET_SECONDS', 0.05), \
                 patch('core.jobs.SUBMISSION_BUDGET_SECONDS', 0.05):
                with patch('core.jobs.httpx.post') as post:
                    self.assertTrue(run_one())
        # Overrunning the budget is a busy host, not a broken recording: the same bytes can succeed next time.
        self.assert_stopped_cleanly(job, post, media.TOO_SLOW, retryable=True)

    def test_a_payload_shorter_than_the_recording_that_was_priced_is_disclosed_in_the_transcript(self):
        """The structural silence: every other arm compares the PROVIDER against what we submitted, so loss that
        happened before the request was invisible by construction."""
        relative = self.enqueue_file('tagged.mp3', '.mp3', 'uploads/short-payload.mp3')
        from core import audio
        bounds = audio.measure_bounds(private_path(relative).read_bytes())
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post', return_value=deepgram(TRANSCRIPT, 'dg_short', duration=SECONDS)):
                self.assertTrue(run_one())
        job.refresh_from_db()
        submitted = Decimal(Usage.objects.get(job=job).units['submitted_seconds'])
        requires_input(bounds.measured - submitted > Decimal(2),
                       'a fixture whose priced ceiling exceeds its submitted audio by more than the tolerance')
        stored = private_path(job.result_path).read_text()
        self.assertIn('could be read as audio', stored)
        self.assertNotIn('was not transcribed', stored, 'the provider must not be blamed for loss before the request')


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class AStructurallyAmbiguousRecordingIsRefusedBeforeAnyCharge(BoundaryFixture, TestCase):
    """A WAV whose samples are split across more than one `data` chunk, refused where multi-track inputs are refused.

    ⚠️ THE FILE GIVES THREE ANSWERS AND NOTHING DECIDES BETWEEN THEM. On a 1 s + 9 s file: core/audio.py's floor says
    1 s, its ceiling says 10 s, and ffmpeg — the decoder of record — plays 9 s, because it reaches the LAST chunk.
    Reverse the chunks and ffmpeg plays 1 s instead. No statement about what was transcribed can rest on that, so it
    is refused before a job exists, exactly like a payload holding several audio tracks.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def store(self, raw, name):
        relative = 'uploads/%s.wav' % name
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return relative

    def test_two_data_chunks_create_no_job_no_hold_and_no_provider_request(self):
        from core import audio
        for first, second in ((9, 1), (1, 9), (5, 5)):
            with self.subTest(chunks='%d+%d' % (first, second)):
                raw = wav_with_two_data_chunks(first, second)
                bounds = audio.measure_bounds(raw)
                requires_input(bool(bounds.ambiguity), 'a fixture the parser actually reports as ambiguous')
                relative = self.store(raw, 'split-%d-%d' % (first, second))
                with patch.dict(os.environ, STANDARD_ENV), patch('core.jobs.httpx.post') as post:
                    with self.assertRaises(ValidationError) as refusal:
                        enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
                self.assertIn('more than one audio data chunk', str(refusal.exception))
                self.assertIn('single continuous audio track', str(refusal.exception))
                self.assertEqual(post.call_count, 0, 'a payload nobody could interpret reached the provider')
                self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 0)
                self.assertEqual(Reservation.objects.count(), 0, 'a refused upload left a reservation outstanding')
                self.assertEqual(Usage.objects.count(), 0)

    def test_an_ordinary_wav_is_not_refused_by_the_same_check(self):
        """The positive control. A refusal that fires on every WAV would pass the test above and break uploads."""
        relative = self.store(wav_bytes(seconds=2, tag='ordinary'), 'ordinary')
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post', return_value=deepgram(TRANSCRIPT, 'dg_ordinary', duration=2)) as post:
                self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(post.call_count, 1)

    def test_trailing_metadata_chunks_are_not_mistaken_for_audio(self):
        """`LIST`/`INFO` and `id3 ` after the audio are metadata, and a writer that emits them is not ambiguous.

        Measured: both carry `ambiguity=''` and their ceiling equals their floor, so nothing here can fire on them.
        """
        import struct
        from core import audio
        base = wav_bytes(seconds=2, tag='meta')
        for label, chunk, body in (('LIST/INFO', b'LIST', b'INFOIART' + struct.pack('<I', 4) + b'anon'),
                                   ('id3', b'id3 ', b'ID3\x03\x00\x00\x00\x00\x00\x00')):
            with self.subTest(trailing=label):
                raw = (base[:4] + struct.pack('<I', struct.unpack('<I', base[4:8])[0] + 8 + len(body))
                       + base[8:] + chunk + struct.pack('<I', len(body)) + body)
                bounds = audio.measure_bounds(raw)
                self.assertEqual(bounds.ambiguity, '', '%s metadata was read as a second audio chunk' % label)
                self.assertEqual(bounds.confirmed, bounds.measured)


class TheArtifactMustDECODE(MediaFixtures, SimpleTestCase):
    """A successful remux is not valid audio, and the two were treated as the same thing.

    `-c:a copy` moves frames without decoding them and exits 0 on a container whose frames no decoder can use;
    ffprobe then reports the duration the CONTAINER DECLARES, which is a header field. So the artifact is now decoded
    and the decoded length compared with the declared one.
    """

    def test_the_decoded_length_is_measured_and_is_not_the_declared_one(self):
        """⚠️ The first version of `decodes()` ended `return probe_submission(path).selected_seconds` — comparing the
        declared duration with itself, a check that could never disagree. These two numbers must genuinely differ."""
        source, destination, _, produced = self.normalise('tone.webm')
        self.assertIsNotNone(produced.decoded_seconds)
        self.assertNotEqual(produced.decoded_seconds, produced.selected_seconds,
                            'declared and decoded are the same number, so one of them is not being measured')
        self.assertAlmostEqual(float(produced.decoded_seconds), SECONDS, places=2)

    def test_every_accepted_format_decodes_to_about_what_it_declares(self):
        for name in ('tone.webm', 'tone.wav', 'tone.mp3', 'tone.m4a'):
            with self.subTest(name=name):
                _, _, _, produced = self.normalise(name)
                drift = abs(produced.decoded_seconds - produced.selected_seconds)
                self.assertLess(drift, media.DECODE_TOLERANCE_SECONDS, name)
                # Measured worst case across five durations and four formats is 0.040 s. A literal, not the constant
                # under test — see MEASURED_WORST_DEVIATION above for why that distinction is load-bearing.
                self.assertLess(drift, Decimal('0.05'), '%s drifted further than any measured recording' % name)

    def test_an_artifact_that_declares_more_than_it_decodes_is_refused(self):
        """⚠️ EXERCISED BY PATCHING, AND THE REASON IS STATED RATHER THAN HIDDEN. I could not build a payload that
        remuxes cleanly, probes cleanly, and still fails to decode: every corruption I attempted damaged the container
        instead, and was caught earlier by ffprobe refusing it or by the loss check. That is a real limit on this
        test, not an argument that the guard is unnecessary — the guard exists for the case where a container's
        declared duration and its contents disagree, and what is proved here is that the comparison fires when they
        do."""
        source = self.media / 'tone.wav'
        upload = probe_submission(source)
        destination = Path(tempfile.mkdtemp(prefix='undecodable-')) / 'out.wav'
        self.addCleanup(shutil.rmtree, destination.parent, True)
        with patch.object(media, 'decodes', lambda path, deadline=None: Decimal('0.5')):
            with self.assertRaises(NotNormalised) as refusal:
                normalise_submission(source, destination, upload)
        self.assertEqual(refusal.exception.kind, media.UNREADABLE)
        self.assertIn('decodes to', refusal.exception.detail)
        self.assertFalse(destination.exists(), 'an artifact that fails verification was left where it could be sent')

    @staticmethod
    def fake_decoder(payload, stderr_line=b''):
        """A decoder whose stdout is a REAL pipe, because the production loop selects on its file descriptor.

        ⚠️ The first version of these used io.BytesIO, which has no fileno(), so adding the `select` deadline broke
        all three at once. A fake that cannot be selected on was never exercising the read path it claimed to.
        """
        def spawn(argv, stdout=None, stderr=None, **kwargs):
            if stderr_line:
                stderr.write(stderr_line)
            read_fd, write_fd = os.pipe()
            with os.fdopen(write_fd, 'wb') as sink:
                sink.write(payload)

            class Decoder:
                returncode = 0

                def __init__(self):
                    self.stdout = os.fdopen(read_fd, 'rb')

                def poll(self):
                    return 0

                def wait(self, timeout=None):
                    return 0

            return Decoder()
        return spawn

    def test_a_decoder_that_reports_anything_at_all_is_a_refusal(self):
        """At `-v error` a clean decode is silent, so any line is a finding — ffmpeg exits 0 on many damaged inputs,
        reporting the damage on stderr and returning success. A returncode check alone would accept a payload that
        lost frames to the decoder while still claiming their duration."""
        spawn = self.fake_decoder(b'\x00' * (media.DECODE_RATE * 2),
                                  b'[opus @ 0x0] Could not update timestamps for skipped samples\n')
        with patch('core.media.subprocess.Popen', spawn):
            with self.assertRaises(NotNormalised) as refusal:
                media.decodes(self.media / 'tone.wav')
        self.assertEqual(refusal.exception.kind, media.UNREADABLE)
        self.assertIn('Could not update timestamps', refusal.exception.detail)

    def test_a_silent_decoder_returning_audio_is_accepted(self):
        """The positive control for the check above: the same path, one second of samples, nothing on stderr."""
        with patch('core.media.subprocess.Popen', self.fake_decoder(b'\x00' * (media.DECODE_RATE * 2))):
            self.assertEqual(media.decodes(self.media / 'tone.wav'), Decimal('1.000'))

    def test_a_decode_that_produces_nothing_is_a_refusal(self):
        """Exit 0, silent stderr, and no samples at all — a container that declares audio and delivers none."""
        with patch('core.media.subprocess.Popen', self.fake_decoder(b'')):
            with self.assertRaises(NotNormalised) as refusal:
                media.decodes(self.media / 'tone.wav')
        self.assertEqual(refusal.exception.kind, media.UNREADABLE)
        self.assertIn('no audio at all', refusal.exception.detail)

    def test_a_decoder_that_produces_nothing_and_never_exits_is_bounded(self):
        """⚠️ THE DEADLINE USED TO BE CHECKED ONLY AFTER A NON-EMPTY READ, so a silent child was never timed out —
        it blocked in read() indefinitely and only the outer watchdog stopped it. This holds a pipe open and writes
        nothing, which is exactly that shape, and it must now return in about the budget rather than never."""
        import time as clock

        def spawn(argv, stdout=None, stderr=None, **kwargs):
            read_fd, write_fd = os.pipe()
            keep = os.fdopen(write_fd, 'wb')            # deliberately never written to and never closed

            class Decoder:
                returncode = 0

                def __init__(self):
                    self.stdout = os.fdopen(read_fd, 'rb')
                    self._keep = keep

                def poll(self):
                    return None

                def kill(self):
                    self._keep.close()

                def wait(self, timeout=None):
                    return 0

            return Decoder()

        # ⚠️ RUN IN A THREAD WITH A JOIN TIMEOUT, because without the guard this call does not return SLOWLY — it
        # does not return AT ALL, and a test that hangs is a worse guard than one that fails. Proved by mutation: with
        # the select removed the read blocks on a pipe that is never written and never closed, and the whole run had
        # to be killed by an outer timeout. This way the assertion is 'it came back', which is the real claim.
        import threading
        outcome = {}

        def attempt():
            try:
                media.decodes(self.media / 'tone.wav', deadline=1.0)
                outcome['kind'] = None
            except NotNormalised as refusal:
                outcome['kind'] = refusal.kind
            except BaseException as error:                       # noqa: BLE001 - recorded, not swallowed
                outcome['kind'] = type(error).__name__

        worker = threading.Thread(target=attempt, daemon=True)
        started = clock.monotonic()
        with patch('core.media.subprocess.Popen', spawn):
            worker.start()
            worker.join(timeout=15)
        elapsed = clock.monotonic() - started
        self.assertFalse(worker.is_alive(),
                         'decodes() never returned on a silent child — the deadline is not enforced')
        self.assertEqual(outcome.get('kind'), media.TOO_SLOW)
        self.assertLess(elapsed, 10, 'the silent-child deadline fired late, after %.1f s' % elapsed)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class UnreadableAndAmbiguousReachTheWorkerAndReleaseExactlyOnce(MediaFixtures, BoundaryFixture, TestCase):
    """The two refusal kinds that had NO evidence past the unit level, exercised where the money is.

    ⚠️ WHAT WAS MISSING, STATED SO THE GAP IS NOT RE-OPENED QUIETLY. `UNREADABLE` is the widest kind in
    `core/media.py` — nine raise sites — and `AMBIGUOUS` is a sixth kind the refusal list did not name.
    Every test either kind had called `probe_submission`, `plan_normalisation` or `normalise_submission`
    DIRECTLY. None called `run_one()`, so no reservation was ever created and no release was ever
    exercised: the assertions proved the CLASSIFIER and said nothing about the MONEY.

    ⚠️ AND THE FIRST VERSION OF THIS CLASS WAS BUILT ON A WRONG ASSUMPTION, WHICH MEASURING CAUGHT. It
    assumed an unreadable upload reaches the worker holding a reservation. It does not: an unprobeable
    payload cannot be priced, so the recording-limit gate refuses it at the HTTP entry point with
    *"The length of this recording could not be determined … Nothing was sent."* — no job, no hold. Both
    outcomes are proved below, each against the path that actually produces it, because a test that
    exercises a path the product does not take is a number rather than evidence.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def upload(self, name, payload, content_type):
        """Through the real HTTP entry point the doctor uses, quote and consent included."""
        with patch.dict(os.environ, STANDARD_ENV):
            page = self.client.get(f'/encounters/{self.encounter.pk}/')
            return self.client.post(f'/encounters/{self.encounter.pk}/voice/', {
                'audio': SimpleUploadedFile(name, payload, content_type=content_type),
                'consent': 'on', 'usage_quote': page.context['usage_quote']}, follow=True)

    def enqueue_file(self, name, suffix, relative=None):
        relative = relative or f'uploads/reservation-{name.replace(".", "-")}{suffix}'
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((self.media / name).read_bytes())
        return relative

    # ---- the proofs the money paths have to satisfy ----------------------------------------------

    def assert_nothing_was_created_or_charged(self, post):
        """For a failure BEFORE enqueue: no job, no reservation, no customer charge, no provider call."""
        from core.models import LedgerEntry, ProviderReceipt
        self.assertEqual(post.call_count, 0, 'the provider was contacted for a refused upload')
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 0)
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertEqual(Usage.objects.count(), 0)
        self.assertEqual(ProviderReceipt.objects.count(), 0)
        self.assertEqual(LedgerEntry.objects.filter(kind='usage').count(), 0)
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.reserved, 0)
        self.assertEqual(self.balances(), (Decimal('10'), Decimal('0')))

    def assert_money_came_back_exactly_once(self, job, post, kind):
        """For a failure AFTER a reservation exists: every proof the item names, in order."""
        from core.management.commands.audit_billing import audit_report
        from core.media import REFUSAL_TEXT
        from core.models import LedgerEntry, ProviderReceipt
        job.refresh_from_db()
        # 1 · no provider request happened
        self.assertEqual(post.call_count, 0, 'the provider was contacted despite a processing failure')
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        # 2 · the job reached the appropriate terminal state, naming the cause to the doctor
        self.assertEqual(job.state, 'failed', job.error)
        self.assertIn(REFUSAL_TEXT[kind], job.error)
        self.assertIn('nothing was charged and the held funds were released', job.error)
        self.assertNotIn('Try again', job.error, 'a cause re-sending the same bytes cannot fix invited a retry')
        # 3 · the reservation was released EXACTLY once — one release row per reservation, never two
        reservations = Reservation.objects.filter(job=job)
        self.assertTrue(reservations.exists(), 'the fixture never held anything, so releasing it proves nothing')
        self.assertEqual([r.state for r in reservations], ['released'] * reservations.count())
        releases = AuditEvent.objects.filter(action='usage.release', target=str(job.pk)).count()
        self.assertEqual(releases, reservations.count(),
                         'the hold was released %d times for %d reservations' % (releases, reservations.count()))
        # 4 · balances and charges are correct: nothing charged, nothing still reserved, nothing moved
        self.assertEqual(Usage.objects.filter(job=job).count(), 0, 'a failure that never reached the provider was charged')
        self.assertEqual(LedgerEntry.objects.filter(job=job).count(), 0)
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.reserved, 0)
        self.assertEqual(self.balances(), (Decimal('10'), Decimal('0')))
        report = audit_report()
        self.assertTrue(report['all_checks_pass'], report['rows'])
        self.assertEqual(report['unresolved_jobs'], [])

    def assert_repeating_the_failure_handling_cannot_release_twice(self, job):
        """⚠️ THE REPLAY IS THE CHECK. One release says nothing about a second call, and a retried worker,
        a crash between the write and the commit, or an administrator resolving an already-failed job all
        reach this path again. `release()` filters on state='held', so a second call is a structural no-op
        — but that is a claim about the code until something actually replays it."""
        from core.billing import release
        before = (Reservation.objects.filter(job=job, state='released').count(),
                  AuditEvent.objects.filter(action='usage.release', target=str(job.pk)).count(),
                  self.balances())
        release(job)
        release(job)
        self.promo.refresh_from_db()
        after = (Reservation.objects.filter(job=job, state='released').count(),
                 AuditEvent.objects.filter(action='usage.release', target=str(job.pk)).count(),
                 self.balances())
        self.assertEqual(after, before, 'replaying the release moved a reservation, an audit row or a balance')
        self.assertEqual(self.promo.reserved, 0)

    def assert_the_encounter_is_still_usable(self):
        """A stopped recording must not strand the visit: the notes still edit and a new job still queues."""
        self.encounter.refresh_from_db()
        edited = self.client.post(f'/encounters/{self.encounter.pk}/notes/',
                                  {'revision': self.encounter.revision, 'notes': 'Symptoms: edited after the refusal'})
        self.assertEqual(edited.status_code, 302, 'the encounter could not be edited after a refused recording')
        self.encounter.refresh_from_db()
        relative = self.enqueue_file('tone.wav', '.wav', f'uploads/after-refusal-{self.encounter.revision}.wav')
        with patch.dict(os.environ, STANDARD_ENV):
            again = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
        self.assertEqual(again.state, 'queued', 'a new recording could not be queued after a refused one')

    # ---- UNREADABLE, before enqueue: the path a real unreadable upload actually takes -------------

    def test_an_unreadable_upload_is_refused_before_anything_is_held(self):
        """MEASURED, and it corrected this class's first assumption.

        A `RIFF` header followed by bytes that are not audio passes the view's signature check, so it gets
        as far as pricing — and there it stops, because a recording whose length cannot be determined
        cannot have a charge limit confirmed. Nothing is queued and nothing is held, which is the stronger
        of the two outcomes.
        """
        with patch('core.jobs.httpx.post') as post:
            response = self.upload('unreadable.wav', b'RIFF' + b'\xff' * 40 + b'GARBAGE' * 400, 'audio/wav')
        self.assertContains(response, 'length of this recording could not be determined')
        self.assertContains(response, 'Nothing was sent')
        self.assert_nothing_was_created_or_charged(post)
        # The refused upload is not kept: bytes nobody can read are not evidence of anything.
        self.assertEqual(sorted(private_path('audio').glob('*')) if private_path('audio').is_dir() else [], [])

    # ---- UNREADABLE, after a reservation exists: the reachable shape that holds money -------------

    def test_a_recording_that_becomes_unreadable_after_the_hold_is_released_by_the_worker(self):
        """REACHABILITY, MEASURED — AND THE MEASURING IS WHY THIS TEST LOOKS LIKE IT DOES.

        Two shapes were tried first and BOTH turned out to be refused before any hold, which is the
        stronger outcome and is proved above: an unprobeable payload, and a `.webm` carrying Vorbis
        instead of Opus. The entry gate refuses them while pricing — *"the length of this recording could
        not be determined (unsupported format)"* and *"(WebM audio that is not Opus)"* — because
        `core/audio.py` parses the container itself and a recording it cannot measure cannot have a charge
        limit confirmed.

        What genuinely reaches the worker holding a reservation is a recording that was fine when it was
        priced and is not fine when it is read: the stored bytes change between enqueue and processing.
        That is the same operational class the `MISSING` kind exists for — its own regression test unlinks
        the file at exactly this point — and it is a storage fault, not a constructed branch.
        """
        relative = self.enqueue_file('tone.wav', '.wav', 'uploads/becomes-unreadable.wav')
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            # Priced and held on bytes that were readable at the time — otherwise there is no release to prove.
            self.assertEqual(job.config['submission_streams'], '1')
            self.assertEqual(Reservation.objects.filter(job=job, state='held').count(), 1)
            # The stored recording is damaged after the hold and before the worker reads it.
            private_path(relative).write_bytes(b'RIFF' + b'\xff' * 40 + b'GARBAGE' * 400)
            with patch('core.jobs.httpx.post') as post:
                self.assertTrue(run_one())
        self.assert_money_came_back_exactly_once(job, post, media.UNREADABLE)
        self.assert_repeating_the_failure_handling_cannot_release_twice(job)
        self.assert_the_encounter_is_still_usable()

    def test_the_entry_gate_is_stricter_than_the_remux_table_and_that_is_recorded_not_assumed(self):
        """⚠️ TWO READERS OF ONE QUESTION — "what audio can this product carry" — and today they disagree.

        `core/audio.py` decides what can be PRICED; `core/media.plan_normalisation` decides what can be
        SUBMITTED. Measured on this host, the pricing gate is the stricter of the two: a `.webm` holding
        Vorbis is refused while pricing, so `plan_normalisation`'s "no lossless remux is defined" branch is
        defence in depth and is not reachable from an upload. That is a fine state to be in — and it is
        recorded here rather than left implicit, because it can stop being true in either direction: a
        codec added to the remux table that pricing still refuses becomes dead code, and a codec pricing
        starts accepting that the table lacks makes this the ONLY guard, holding a reservation when it
        fires. The pairing is the finding; this asserts it so a change to either side has to face it.
        """
        from core.media import CONTAINERS
        self.assertNotIn('vorbis', CONTAINERS, 'the remux table gained vorbis; check the pricing gate accepts it too')
        with patch('core.jobs.httpx.post') as post:
            response = self.upload('vorbis.webm', (self.media / 'vorbis.webm').read_bytes(), 'audio/webm')
        self.assertContains(response, 'length of this recording could not be determined')
        self.assertContains(response, 'WebM audio that is not Opus')
        self.assert_nothing_was_created_or_charged(post)

    def test_the_same_journey_with_a_supported_codec_is_not_refused(self):
        """The positive control. A worker that refused every recording would pass the test above."""
        relative = self.enqueue_file('tone.webm', '.webm', 'uploads/opus-control.webm')
        response = deepgram(TRANSCRIPT, 'dg_opus_control', duration=SECONDS)
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post', return_value=response) as post:
                self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(post.call_count, 1, 'the control never reached the provider, so the refusal proves nothing')
        self.assertEqual(job.state, 'succeeded', job.error)

    # ---- AMBIGUOUS, past the enqueue guard, in the worker ----------------------------------------

    def test_a_payload_that_becomes_ambiguous_after_the_hold_releases_it(self):
        """REACHABILITY, AND ITS CONDITION, STATED PLAINLY RATHER THAN IMPLIED.

        `enqueue` refuses a multi-track payload before any hold, and
        `AmbiguousInputIsRefusedBeforeAnythingIsPaidFor` proves that through the same HTTP entry point —
        that is the path a doctor meets. `plan_normalisation`'s `AMBIGUOUS` is therefore DEFENCE IN DEPTH,
        reachable only when the stream count is unknown at enqueue and known at processing:
        `describe_submission` records `unprobeable` and skips the count guard when the probe does not
        answer, and a probe timeout on a loaded shared host is how that happens. That is the sequence
        below — the probe fails once, at enqueue, and the real one runs in the worker.

        It is exercised because the branch RELEASES MONEY, not to raise a number: if the two guards ever
        disagree about what is ambiguous, this is the one holding a reservation when it fires.
        """
        relative = self.enqueue_file('two-tracks.webm', '.webm', 'uploads/late-ambiguous.webm')
        real_probe = media.probe_submission
        calls = {'n': 0}

        def probe_fails_only_at_enqueue(*args, **kwargs):
            calls['n'] += 1
            if calls['n'] == 1:
                raise media.SubmissionUnprobeable(media.UNAVAILABLE, 'the probe did not answer in time')
            return real_probe(*args, **kwargs)
        with patch.dict(os.environ, STANDARD_ENV):
            with patch('core.jobs.probe_submission', side_effect=probe_fails_only_at_enqueue):
                job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
                # The enqueue guard was skipped because the count was unknown — which is why a hold exists.
                self.assertEqual(job.config['submission_status'], 'unprobeable')
                self.assertEqual(job.config['submission_streams'], '')
                self.assertEqual(Reservation.objects.filter(job=job, state='held').count(), 1)
                with patch('core.jobs.httpx.post') as post:
                    self.assertTrue(run_one())
        requires_input(calls['n'] >= 2, 'the worker to have probed as well, or the refusal came from the wrong call')
        self.assert_money_came_back_exactly_once(job, post, media.AMBIGUOUS)
        self.assert_repeating_the_failure_handling_cannot_release_twice(job)
        self.assert_the_encounter_is_still_usable()

    def test_the_worker_names_ambiguous_rather_than_borrowing_another_kind(self):
        """`AMBIGUOUS` and `UNREADABLE` say different things to a doctor: one recording has two answers,
        the other has none. A refusal reporting the wrong one would still release the money and still pass
        every assertion above, so the distinction is asserted rather than assumed."""
        from core.media import REFUSAL_TEXT
        self.assertNotEqual(REFUSAL_TEXT[media.AMBIGUOUS], REFUSAL_TEXT[media.UNREADABLE])
        self.assertNotIn(media.AMBIGUOUS, media.RETRYABLE, 'a second identical upload cannot fix two tracks')
        self.assertNotIn(media.UNREADABLE, media.RETRYABLE)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class TheBillingAuditActuallyDETECTSStrandedFunds(BoundaryFixture, TestCase):
    """⚠️ EVERY TEST ABOVE ENDS BY ASSERTING `all_checks_pass`. THIS IS WHAT MAKES THAT MEAN SOMETHING.

    A green audit is evidence only if a red one is reachable. If `audit_report()` could not see a hold
    that outlived its job, then every `assertTrue(report['all_checks_pass'])` in this file would be a
    control from a different era — true, cheap, and blind to the one failure the release path exists to
    prevent. So the stranded reservation is planted deliberately, in an isolated fixture, and the audit
    has to find it.

    The plant is the exact shape a half-applied refusal leaves behind: the job ends, the money does not
    come back. It is created by writing the rows directly rather than by breaking `release()`, because the
    subject here is the AUDIT, not the release path — and a mutation of `release()` would prove the audit
    catches one specific bug rather than the state itself.
    """

    def strand_a_reservation(self):
        """A job that ended while its reservation is still held — funds nobody can see from the outside."""
        from core.billing import reserve
        relative = f'uploads/stranded-{self.encounter.revision}.wav'
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(wav_bytes(tag='stranded'))
        with patch.dict(os.environ, self.VOICE_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
        # The job ends. The hold does not — which is precisely the state that must not pass unnoticed.
        Job.objects.filter(pk=job.pk).update(state='failed')
        job.refresh_from_db()
        return job

    def test_a_green_audit_is_reachable_before_the_plant(self):
        """The other half of the control: the fixture is green to start with, so the red below is caused
        by the plant and not by the fixture being broken all along."""
        from core.management.commands.audit_billing import audit_report
        report = audit_report()
        self.assertTrue(report['all_checks_pass'], report['wallets'])
        self.assertEqual(report['hold_policy']['ended_jobs_holding_funds'], [])

    def test_an_ended_job_still_holding_funds_turns_the_audit_red(self):
        from core.management.commands.audit_billing import audit_report
        job = self.strand_a_reservation()
        held = Reservation.objects.get(job=job)
        self.assertEqual(held.state, 'held', 'the plant did not actually leave a hold outstanding')
        report = audit_report()
        self.assertFalse(report['all_checks_pass'], 'a green audit concealed a hold that outlived its job')
        self.assertFalse(report['hold_policy']['checks']['ended_jobs_hold_no_funds'])
        self.assertIn(str(job.pk), report['hold_policy']['ended_jobs_holding_funds'])

    def test_the_command_exits_non_zero_so_a_scheduled_run_cannot_pass_over_it(self):
        """A report nobody reads is not a control. The command has to FAIL, not merely print red."""
        from django.core.management import call_command
        from django.core.management.base import CommandError
        self.strand_a_reservation()
        with self.assertRaises(CommandError) as refusal:
            call_command('audit_billing')
        self.assertIn('Billing evidence mismatch', str(refusal.exception))

    def test_releasing_the_stranded_hold_turns_the_audit_green_again(self):
        """The repair closes it. Without this, the test above could be passing because the audit is red
        for some unrelated standing reason rather than because of the plant."""
        from core.billing import release
        from core.management.commands.audit_billing import audit_report
        job = self.strand_a_reservation()
        self.assertFalse(audit_report()['all_checks_pass'])
        release(job)
        report = audit_report()
        self.assertTrue(report['all_checks_pass'], report['wallets'])
        self.assertEqual(report['hold_policy']['ended_jobs_holding_funds'], [])
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.reserved, 0)
        self.assertEqual(self.balances(), (Decimal('10'), Decimal('0')))

    def test_the_wallet_invariant_sees_it_too_when_the_counter_is_the_thing_that_drifts(self):
        """A second, independent reader of the same fact. `reserved_equals_holds` compares the wallet's
        counter against the sum of its held rows, so a counter that drifts from the rows — the shape a
        double release leaves — is caught even when no job has ended."""
        from core.management.commands.audit_billing import audit_report
        self.assertTrue(audit_report()['all_checks_pass'])
        Wallet.objects.filter(pk=self.promo.pk).update(reserved=Decimal('0.25'))
        report = audit_report()
        self.assertFalse(report['all_checks_pass'], 'a wallet reserving funds no reservation explains passed')
        drifted = [w for w in report['wallets'] if w['wallet_id'] == str(self.promo.pk)][0]
        self.assertFalse(drifted['checks']['reserved_equals_holds'])
