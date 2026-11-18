from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from django.core.management.base import CommandError
from workspace.models import Member
class Command(BaseCommand):
    help='Create/update a local Django login and provision it as Techfinitys Super Admin.'
    def add_arguments(self,p):
        p.add_argument('--username',default='admin'); p.add_argument('--password',default='admin12345'); p.add_argument('--email',default='')
    def handle(self,*args,**o):
        if not settings.DEBUG and o['password']=='admin12345':
            raise CommandError('A secure explicit --password is required in production')
        u,_=User.objects.get_or_create(username=o['username'],defaults={'email':o['email'],'is_staff':True,'is_superuser':True})
        u.is_staff=True; u.is_superuser=True
        if o['email']: u.email=o['email']
        u.set_password(o['password']); u.save()
        Member.objects.update_or_create(user=u,defaults={'role':'admin','client':'','permissions':[]})
        self.stdout.write(self.style.SUCCESS(f'Provisioned {u.username} as Techfinitys Super Admin. Change the password for non-local use.'))
