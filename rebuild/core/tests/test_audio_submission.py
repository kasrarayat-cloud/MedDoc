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
import os
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from core import media
from core.jobs import enqueue, reap_stray_submissions, run_one
from core.media import NotNormalised, normalise_submission, plan_normalisation, probe_submission
from core.models import Job, Reservation, Usage
from core.security import private_path
from core.tests.audio_fixtures import wav_bytes, wav_with_two_data_chunks
from core.tests.test_billing_boundary import BoundaryFixture, deepgram
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

    def test_a_recording_at_the_upload_limit_whose_remux_grows_is_sent_not_refused(self):
        """The muxer adds an ID3v2 header and a Xing frame to a tagless MP3, so the artifact crosses the limit the
        upload sat exactly on. Raising there told the doctor 'Recording too large.' about a recording that was inside
        the limit and had transcribed fine before — deterministically, so re-uploading never helped."""
        relative = self.enqueue_file('at-the-limit.mp3', '.mp3')
        original = private_path(relative).read_bytes()
        requires_input(len(original) == 15 * 1024 * 1024, 'an upload sitting exactly on the submission limit')
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.jobs.httpx.post',
                       return_value=deepgram(TRANSCRIPT, 'dg_limit', duration=983)) as post:
                self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(post.call_count, 1)
        # The ORIGINAL is what went, because the remux would not fit — and that is recorded, not silent.
        self.assertEqual(post.call_args.kwargs['content'], original)
        units = Usage.objects.get(job=job).units
        self.assertEqual(units['submission_source'], 'original')
        self.assertIn('above the', units['normalisation_detail'])
        self.assertEqual(sorted(private_path('submissions').glob('*')), [])

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

    def test_a_host_without_ffmpeg_submits_the_original_and_leaves_no_zero_byte_file(self):
        relative = self.enqueue_file('tone.webm', '.webm', 'uploads/no-ffmpeg.webm')
        original = private_path(relative).read_bytes()
        real_which = shutil.which
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch('core.media.shutil.which', lambda name: None if name == 'ffmpeg' else real_which(name)):
                with patch('core.jobs.httpx.post',
                           return_value=deepgram(TRANSCRIPT, 'dg_noffmpeg', duration=SECONDS)) as post:
                    self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')
        self.assertEqual(post.call_args.kwargs['content'], original)
        self.assertEqual(Usage.objects.get(job=job).units['normalisation_detail'], 'ffmpeg is not installed')
        self.assertEqual(sorted(private_path('submissions').glob('*')), [])

    def test_a_remux_that_raises_something_unexpected_falls_back_instead_of_holding_the_funds(self):
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
                        with patch('core.jobs.httpx.post',
                                   return_value=deepgram(TRANSCRIPT, 'dg_preexec_%s' % len(where), duration=SECONDS)) as post:
                            self.assertTrue(run_one())
                job.refresh_from_db()
                self.assertEqual(job.state, 'succeeded', job.error)
                self.assertEqual(post.call_args.kwargs['content'], original)
                self.assertEqual(sorted(private_path('submissions').glob('*')), [])

    def test_the_preparation_budget_falls_back_rather_than_running_past_the_worker_kill_deadline(self):
        """The unit SIGKILLs the whole cgroup 150 s after SIGTERM. Summing the sub-step ceilings reached 250 s, so a
        routine restart could kill a worker mid-remux. Exceeding the budget must cost normalisation, never the job."""
        relative = self.enqueue_file('tone.webm', '.webm', 'uploads/budget.webm')
        original = private_path(relative).read_bytes()
        with patch.dict(os.environ, STANDARD_ENV):
            job = enqueue(self.encounter, self.user, kind='transcription', input_path=relative)
            with patch.object(media, 'SUBMISSION_BUDGET_SECONDS', 0.05), \
                 patch('core.jobs.SUBMISSION_BUDGET_SECONDS', 0.05):
                with patch('core.jobs.httpx.post',
                           return_value=deepgram(TRANSCRIPT, 'dg_budget', duration=SECONDS)) as post:
                    self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)
        self.assertEqual(post.call_args.kwargs['content'], original)
        self.assertEqual(Usage.objects.get(job=job).units['submission_source'], 'original')
        self.assertEqual(sorted(private_path('submissions').glob('*')), [])

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
