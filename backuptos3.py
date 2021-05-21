from datetime import datetime
from pathlib import Path
import zipfile
import argparse
import os
import boto3
import os.path
from cryptography.fernet import Fernet

# connect to s3 with aws cli credentials already configured.
s3 = boto3.resource('s3')

#Argparse argument for directory
def dir_path(path):
    if os.path.isdir(path) or os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"readable_dir:{path} is not a valid path")

#To check if bucket exists
def existing_bucket(self):
    for bucket in s3.buckets.all():
        EXISTING_BUCKETS = bucket.name
    if self in EXISTING_BUCKETS:
        return self
    else:
        raise argparse.ArgumentTypeError(f"bucket name:{self} is not a valid bucket. Please check if bucket exists or you have the correct region")
        

#Parse command line arguments
parser = argparse.ArgumentParser(description=' Scripts backups desired file/folder, encrypt it and stores to S3 bucket')
parser.add_argument('-a','--amount', help='Max amount of backups stored on s3. Default value is 5. Oldest backup will be deleted if exceeded', required=False, default=5, type=int)
parser.add_argument('-o','--objtobckp', help='Object or directory to be backed up', required=True, type=dir_path)
parser.add_argument('-b','--bucket', help='Your S3 bucket name you want to store backups in', required=True, type=existing_bucket)
parser.add_argument('-k','--encryptkey', help='Encryption key location if already have one', required=False, type=dir_path)
parser.add_argument('-ck','--createkey', help='Create key.key file in desired location for encryption/decryption', required=False)
parser.add_argument('-bd','--backupdir', help='Temporary backup directory. Default is /tmp/', required=False, default="/tmp/")
args = parser.parse_args()
if not (args.encryptkey or args.createkey):
    parser.error('Please enter current Encryption key location key.key -k  or specify location to create encryption key -ck')

KEY_FILE_NAME = "key.key"  # encryption key file name
MAX_BACKUP_AMOUNT = args.amount   # The maximum amount of backups to have in S3
OBJECT_TO_BACKUP = args.objtobckp  # The file or directory to backup
bucket_name = args.bucket  #bucket name on S3 that will store backups
BACKUP_DIRECTORY = args.backupdir  # The location to store the backups before moving to S3

#Check if entered key exists
if args.encryptkey:
    LOCATIONFILE = args.encryptkey
    FULL_FILE_PATH = os.path.join(LOCATIONFILE, KEY_FILE_NAME)
    if os.path.isfile(FULL_FILE_PATH) is False:
        parser.error(f"key.key file not found in {args.encryptkey} . Please check the directory or use -ck to create new key")

#Check if key exists and if not, create in desired directory
if args.createkey:
    LOCATIONFILE = args.createkey
    FULL_FILE_PATH = os.path.join(LOCATIONFILE, KEY_FILE_NAME)
    if os.path.isfile(FULL_FILE_PATH):
        parser.error(f"key.key file already exists. Use -k option instead of -ck or choose another directory to create key")
    else:
        key = Fernet.generate_key()
        p = Path(LOCATIONFILE)
        p.mkdir(parents=True,exist_ok=True)
        FULL_FILE_PATH = os.path.join(LOCATIONFILE, KEY_FILE_NAME)
        file = open(FULL_FILE_PATH, 'wb')  # Open the file as wb to write bytes
        file.write(key)  # The key is type bytes still
        file.close()
#Check if temporary backup directory exists, if not create:
if os.path.isdir(args.backupdir)is False:
    os.makedirs(args.backupdir) 

object_to_backup_path = Path(OBJECT_TO_BACKUP)
backup_directory_path = Path(BACKUP_DIRECTORY)
assert object_to_backup_path.exists()  # Validate the object we are about to backup exists before we continue

# Validate the backup directory exists and create if required
backup_directory_path.mkdir(parents=True, exist_ok=True)

# Get the amount of past backup zips in S3
my_bucket = s3.Bucket(bucket_name)
existing_backups = list(object.key for object in my_bucket.objects.all()
            if object.key.startswith('backup-') and object.key.endswith('.zip'))

# Enforce max backups and delete oldest if there will be too many after the new backup
oldest_to_newest_backup_by_name = list(sorted(existing_backups))
while len(oldest_to_newest_backup_by_name) >= MAX_BACKUP_AMOUNT:  
    s3.Object(bucket_name, backup_to_delete).delete()
    existing_backups = list(object.key for object in my_bucket.objects.all()
            if object.key.startswith('backup-') and object.key.endswith('.zip'))
    oldest_to_newest_backup_by_name = list(sorted(existing_backups))

# Create zip file (for both file and folder options)
backup_file_name = f'{datetime.now().strftime("%Y%m%d%H%M%S")}-{object_to_backup_path.name}.zip'
zip_file = zipfile.ZipFile(str(backup_directory_path / backup_file_name), mode='w')
if object_to_backup_path.is_file():
    # If the object to write is a file, write the file
    zip_file.write(
        object_to_backup_path.absolute(),
        arcname=object_to_backup_path.name,
        compress_type=zipfile.ZIP_DEFLATED
    )
elif object_to_backup_path.is_dir():
    # If the object to write is a directory, write all the files
    for file in object_to_backup_path.glob('**/*'):
        if file.is_file():
            zip_file.write(
                file.absolute(),
                arcname=str(file.relative_to(object_to_backup_path)),
                compress_type=zipfile.ZIP_DEFLATED
            )
# Close the created zip file
zip_file.close()

#Encrypt files
source_path = os.path.join(BACKUP_DIRECTORY, backup_file_name)
encrypted_backup_file_name = f'backup-{datetime.now().strftime("%Y%m%d%H%M%S")}-{object_to_backup_path.name}.zip'
source_path_encrypted = os.path.join(BACKUP_DIRECTORY, encrypted_backup_file_name)

file = open(FULL_FILE_PATH, 'rb')  # Open the file as wb to read bytes
key = file.read()  # The key will be type bytes
file.close()
input_file = source_path
output_file = source_path_encrypted
with open(input_file, 'rb') as f:
    data = f.read()  # Read the bytes of the input file
fernet = Fernet(key)
encrypted = fernet.encrypt(data)
with open(output_file, 'wb') as f:
    f.write(encrypted)  # Write the encrypted bytes to the output file


#upload file to S3
s3.meta.client.upload_file(output_file, bucket_name, encrypted_backup_file_name)

#Check if file uploaded successfuly and delete the ones stored on the OS
my_bucket = s3.Bucket(bucket_name)
EXISTING_FILES=(list(object.key for object in my_bucket.objects.all()
            if object.key.startswith('backup-') and object.key.endswith('.zip')))
if encrypted_backup_file_name in EXISTING_FILES:
    os.remove(source_path)
    os.remove(source_path_encrypted)


