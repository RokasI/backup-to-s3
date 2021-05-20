# backup-to-s3
Python script to zip file/folder, encrypt it and send to S3 for storage

# Requirements
    pip install awscli
    pip install boto3
    pip install cryptography

Configured AWS profile with access key, secret key and region where your bucket resides
Example:
#~/.aws/config

#AWS Access Key ID [None]: accesskey
#AWS Secret Access Key [None]: secretkey
#Default region name [None]: us-west-2
#Default output format [None]

# Running an Encrypted Backup:
Please make sure to run backuptos3.py --help to get the most up-to-date instructions on how the command-line parameters work.
Parameters:
    -a  -- Max amount of backups stored on s3. Default value is 5 if limit is exceeded, oldest backup will be deleted.
    -o  -- File or directorory location to be beacked up
    -b  -- S3 bucket name you want to store backups in
    -ck -- Specify location to create encryption key. It will be stored there for decryption
    -k  -- Encryption key location if you already created one
    -db -- Temporary directory to store backed up files before sending to S3. Default is /tmp/


# Example of code run:
      python3 backuptos3.py -a 7 -b your_bucket_name -o /home/ec2-user/files -ck /home/ec2-user/encryptionkey -bd /tmp/temporary-backup
script will backup /home/ec2-user/file directory
amount of backups to store max is set to 7
encryption key will be created and stored in /home/ec2-user/encryptionkey
temporary backup folder will be /tmp/temporary-backup
