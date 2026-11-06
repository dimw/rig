"""
Basic storage operations tests
Converted from test_storage.sh
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def s3_credentials():
    """Setup S3 credentials for StorageManager"""
    os.environ['HETZNER_S3_ACCESS_KEY'] = 'test-access-key'
    os.environ['HETZNER_S3_SECRET_KEY'] = 'test-secret-key'
    yield
    os.environ.pop('HETZNER_S3_ACCESS_KEY', None)
    os.environ.pop('HETZNER_S3_SECRET_KEY', None)


class TestBasicStorageOperations:
    """Test basic storage operations"""

    def test_list_buckets_command(self, hetzner_token, s3_credentials):
        """Test list buckets command"""
        from cli.storage import StorageManager

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.list_buckets.return_value = {
                'Buckets': [{'Name': 'test-bucket-1'}, {'Name': 'test-bucket-2'}]
            }

            storage = StorageManager()
            buckets = storage.list_buckets()

            assert isinstance(buckets, list)
            assert len(buckets) == 2
            assert 'test-bucket-1' in buckets
            assert 'test-bucket-2' in buckets

    def test_create_bucket_command(self, hetzner_token, test_bucket_name):
        """Test create bucket command"""
        from cli.storage import StorageManager

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.create_bucket.return_value = True
            mock_s3.head_bucket.return_value = {}

            storage = StorageManager()
            result = storage.create_bucket(test_bucket_name)

            assert result is True
            mock_s3.create_bucket.assert_called_once_with(Bucket=test_bucket_name)
            mock_s3.head_bucket.assert_called_with(Bucket=test_bucket_name)
            # Hetzner needs path-style + SigV4 on every client (create and upload).
            kwargs = mock_boto.call_args.kwargs
            assert kwargs.get("region_name") == "fsn1"
            assert kwargs["config"].s3.get("addressing_style") == "path"
            assert kwargs["config"].signature_version == "s3v4"

    def test_upload_file_command(self, hetzner_token, s3_credentials, test_bucket_name, test_file):
        """Test upload file command"""
        from cli.storage import StorageManager

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.upload_file.return_value = True

            storage = StorageManager()
            result = storage.upload_file(test_bucket_name, test_file, 'test_object.txt')

            assert result is True
            mock_s3.upload_file.assert_called_once()

    def test_list_objects_command(self, hetzner_token, s3_credentials, test_bucket_name):
        """Test list objects command"""
        from cli.storage import StorageManager

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.list_objects_v2.return_value = {
                'Contents': [
                    {'Key': 'file1.txt', 'Size': 100},
                    {'Key': 'file2.txt', 'Size': 200}
                ]
            }

            storage = StorageManager()
            objects = storage.list_objects(test_bucket_name, '')

            assert isinstance(objects, list)
            assert len(objects) == 2
            assert objects[0] == 'file1.txt'

    def test_download_file_command(self, hetzner_token, s3_credentials, test_bucket_name, tmp_path):
        """Test download file command"""
        from cli.storage import StorageManager

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3

            # Create a temporary file to simulate download
            download_path = str(tmp_path / "downloaded.txt")

            # Mock the download_file method
            def mock_download_file(Bucket, Key, Filename):
                with open(Filename, 'w') as f:
                    f.write("Downloaded content")

            mock_s3.download_file = mock_download_file

            storage = StorageManager()
            result = storage.download_file(test_bucket_name, 'test_object.txt', download_path)

            assert os.path.exists(download_path)
            with open(download_path, 'r') as f:
                content = f.read()
            assert content == "Downloaded content"

    def test_delete_object_command(self, hetzner_token, s3_credentials, test_bucket_name):
        """Test delete object command"""
        from cli.storage import StorageManager

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.delete_object.return_value = True

            storage = StorageManager()
            result = storage.delete_object(test_bucket_name, 'test_object.txt')

            assert result is True
            mock_s3.delete_object.assert_called_once_with(
                Bucket=test_bucket_name, Key='test_object.txt'
            )

    def test_delete_bucket_command(self, hetzner_token, s3_credentials, test_bucket_name):
        """Test delete bucket command"""
        from cli.storage import StorageManager

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.delete_bucket.return_value = True

            storage = StorageManager()
            result = storage.delete_bucket(test_bucket_name)

            assert result is True
            mock_s3.delete_bucket.assert_called_once_with(Bucket=test_bucket_name)


class TestStorageErrorHandling:
    """Test storage error handling"""

    def test_list_buckets_with_error(self, hetzner_token, s3_credentials):
        """Test list buckets with S3 error"""
        from cli.storage import StorageManager
        from botocore.exceptions import ClientError

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.list_buckets.side_effect = ClientError(
                error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
                operation_name='ListBuckets'
            )

            storage = StorageManager()
            buckets = storage.list_buckets()

            # Should return empty list on error
            assert isinstance(buckets, list)

    def test_create_bucket_with_existing(self, hetzner_token, s3_credentials, test_bucket_name):
        """Test create bucket when bucket already exists"""
        from cli.storage import StorageManager
        from botocore.exceptions import ClientError

        with patch('boto3.client') as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.create_bucket.side_effect = ClientError(
                error_response={'Error': {'Code': 'BucketAlreadyOwnedByYou', 'Message': 'Bucket already exists'}},
                operation_name='CreateBucket'
            )

            storage = StorageManager()
            result = storage.create_bucket(test_bucket_name)

            # Should handle existing bucket gracefully
            assert result is True  # Or handle as appropriate
            mock_s3.head_bucket.assert_called_with(Bucket=test_bucket_name)

    def test_create_bucket_waits_through_eventual_consistency(
        self, hetzner_token, s3_credentials, test_bucket_name
    ):
        """HeadBucket 404s briefly after CreateBucket before the bucket is ready."""
        from cli.storage import StorageManager
        from botocore.exceptions import ClientError

        not_ready = ClientError(
            error_response={
                "Error": {"Code": "404", "Message": "Not Found"},
                "ResponseMetadata": {"HTTPStatusCode": 404},
            },
            operation_name="HeadBucket",
        )

        with patch("boto3.client") as mock_boto, patch("cli.storage.time.sleep") as mock_sleep:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.create_bucket.return_value = True
            mock_s3.head_bucket.side_effect = [not_ready, not_ready, {}]

            storage = StorageManager()
            assert storage.create_bucket(test_bucket_name) is True
            assert mock_s3.head_bucket.call_count == 3
            assert mock_sleep.call_count == 2

    def test_create_bucket_retries_location_constraint(
        self, hetzner_token, s3_credentials, test_bucket_name
    ):
        """Retry CreateBucket once when Hetzner reports LocationConstraintConflict."""
        from cli.storage import StorageManager
        from botocore.exceptions import ClientError

        conflict = ClientError(
            error_response={
                "Error": {
                    "Code": "InvalidLocationConstraint",
                    "Message": "LocationConstraintConflict for bucket",
                }
            },
            operation_name="CreateBucket",
        )

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.create_bucket.side_effect = [conflict, True]
            mock_s3.head_bucket.return_value = {}

            storage = StorageManager()
            assert storage.create_bucket(test_bucket_name) is True
            assert mock_s3.create_bucket.call_count == 2

    def test_create_bucket_returns_false_when_wait_times_out(
        self, hetzner_token, s3_credentials, test_bucket_name
    ):
        """create_bucket fails closed if the bucket never becomes visible."""
        from cli.storage import StorageManager

        with patch("boto3.client") as mock_boto, patch(
            "cli.storage.StorageManager._wait_for_bucket", return_value=False
        ):
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.create_bucket.return_value = True

            storage = StorageManager()
            assert storage.create_bucket(test_bucket_name) is False

    def test_delete_object_missing_key_is_ok(
        self, hetzner_token, s3_credentials, test_bucket_name
    ):
        from cli.storage import StorageManager
        from botocore.exceptions import ClientError

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.delete_object.side_effect = ClientError(
                error_response={"Error": {"Code": "NoSuchKey", "Message": "gone"}},
                operation_name="DeleteObject",
            )

            storage = StorageManager()
            assert storage.delete_object(test_bucket_name, "missing.txt") is True

    def test_endpoint_region_from_url(self, hetzner_token, s3_credentials):
        from cli.storage import StorageManager

        storage = StorageManager(endpoint_url="https://hel1.your-objectstorage.com")
        assert storage._endpoint_region() == "hel1"
        storage.endpoint_url = "https://nbg1.your-objectstorage.com"
        assert storage._endpoint_region() == "nbg1"
        storage.endpoint_url = "https://objects.example.com"
        assert storage._endpoint_region() == "fsn1"
