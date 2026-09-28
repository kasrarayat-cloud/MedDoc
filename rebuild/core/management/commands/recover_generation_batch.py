"""Revalidate a fully recorded interrupted batch without any provider request."""
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError, PermissionDenied
from core.batch_jobs import recover_recorded
from core.models import User, GenerationBatch


class Command(BaseCommand):
    help='Explicit local-only recovery of all durable batch responses; never repeats a provider attempt.'

    def add_arguments(self,parser):
        parser.add_argument('--batch',required=True)
        parser.add_argument('--administrator',required=True)
        parser.add_argument('--recorded-only',required=True,action='store_true')

    def handle(self,*args,**options):
        try:
            user=User.objects.get(pk=options['administrator'])
            recover_recorded(options['batch'],user)
            batch=GenerationBatch.objects.get(pk=options['batch'])
        except (ValueError,ValidationError,PermissionDenied,User.DoesNotExist,GenerationBatch.DoesNotExist) as error:
            raise CommandError('Recorded batch recovery refused: '+type(error).__name__) from None
        self.stdout.write(f'Batch {batch.pk}: {batch.state}. No provider request was made.')
