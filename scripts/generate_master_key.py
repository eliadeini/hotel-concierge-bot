"""Print a fresh Fernet master key for MASTER_ENCRYPTION_KEY in .env."""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    print(Fernet.generate_key().decode())
