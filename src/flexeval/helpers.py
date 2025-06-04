import datetime
import hashlib


def generate_hash():
    """Create a random 8-digit id"""
    # Create a new SHA-256 hash object
    hash_object = hashlib.sha256()

    # Update the hash object with the bytes of the string
    hash_object.update(datetime.datetime.now().isoformat().encode())

    # Get the hexadecimal digest of the hash
    full_hash = hash_object.hexdigest()

    # Return the first 8 digits of the hash
    return full_hash[:8]
