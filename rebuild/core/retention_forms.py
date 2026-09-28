import uuid
from django import forms

class HoldForm(forms.Form):
    scope=forms.ChoiceField(choices=[('patient','Patient'),('encounter','Document'),('department','Department'),('organization','Organization'),('global','All clinical data')])
    target=forms.UUIDField(required=False,label='Record ID',help_text='Copy the ID from the authorized record. Leave blank only for all clinical data.')
    authority_sha256=forms.RegexField(regex=r'\A[0-9a-f]{64}\Z',max_length=64,label='Authority document SHA-256',help_text='Fingerprint of the recorded preservation instruction. Keep its signed original with the authorized custodian.',widget=forms.TextInput(attrs={'spellcheck':'false','autocomplete':'off'}))
    request_key=forms.UUIDField(initial=uuid.uuid4,widget=forms.HiddenInput)
    confirmed=forms.BooleanField(label='I checked the scope and have recorded authority to preserve this data.')

    def clean(self):
        data=super().clean()
        if data.get('scope')=='global' and data.get('target'):self.add_error('target','All clinical data has no individual record ID.')
        elif data.get('scope')!='global' and not data.get('target'):self.add_error('target','Choose the exact record to preserve.')
        return data

class ReleaseForm(forms.Form):
    hold=forms.UUIDField(label='Hold ID')
    authority_sha256=forms.RegexField(regex=r'\A[0-9a-f]{64}\Z',max_length=64,label='Release authority SHA-256',widget=forms.TextInput(attrs={'spellcheck':'false','autocomplete':'off'}))
    confirmed=forms.BooleanField(label='I am a second custodian and have recorded authority to end this hold. Preserved evidence stays retained.')
