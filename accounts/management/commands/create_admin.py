# accounts/management/commands/create_admin.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from getpass import getpass
import sys

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superadmin user with proper permissions'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Create DukaLink Superadmin ==='))
        
        # Get user details
        username = input('Username: ')
        email = input('Email: ')
        password = getpass('Password: ')
        password2 = getpass('Confirm Password: ')
        
        if password != password2:
            self.stdout.write(self.style.ERROR('Passwords do not match!'))
            sys.exit(1)
        
        # Check if user exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'User "{username}" already exists!'))
            sys.exit(1)
        
        # Create superuser
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Superadmin "{username}" created successfully!')
        )
        self.stdout.write(f'You can now login at /admin-panel/')