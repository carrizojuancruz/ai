import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, List

import boto3
from langchain_core.documents import Document

from app.core.config import config

logger = logging.getLogger(__name__)


class S3SyncService:
    """Service for managing S3 files and syncing them to the vector store."""

    def __init__(self):
        self.bucket_name = config.S3V_KB_S3_FILES
        self.s3_client = boto3.client('s3', region_name=config.AWS_REGION)

        self._vector_service = None
        self._document_service = None

    @property
    def vector_service(self):
        """Lazy initialization of vector store service."""
        if self._vector_service is None:
            from app.knowledge.vector_store.service import S3VectorStoreService
            self._vector_service = S3VectorStoreService()
        return self._vector_service

    @property
    def document_service(self):
        """Lazy initialization of document service."""
        if self._document_service is None:
            from app.knowledge.document_service import DocumentService
            self._document_service = DocumentService()
        return self._document_service

    def upload_file(self, local_path: str, s3_key: str | None = None) -> Dict[str, Any]:
        """Upload a file to S3 bucket.

        Args:
            local_path: Path to local file to upload
            s3_key: Optional S3 key (defaults to filename)

        Returns:
            Dict with success status, s3_key, s3_uri, bucket

        """
        try:
            if s3_key is None:
                s3_key = Path(local_path).name

            content_type = self._get_content_type(local_path)

            self.s3_client.upload_file(
                local_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )

            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Successfully uploaded {local_path} to {s3_uri}")

            return {
                "success": True,
                "s3_key": s3_key,
                "s3_uri": s3_uri,
                "bucket": self.bucket_name,
                "content_type": content_type
            }

        except Exception as e:
            error_type = type(e).__name__
            if error_type == 'ClientError':
                logger.error(f"S3 error during upload: {str(e)}")
            else:
                logger.error(f"Unexpected error during upload: {str(e)}")

            return {
                "success": False,
                "error": str(e),
                "s3_key": s3_key
            }

    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List all files in S3 bucket with optional prefix filter.

        Args:
            prefix: Optional prefix to filter files

        Returns:
            List of dicts with s3_key, size, size_mb, last_modified, s3_uri

        """
        try:
            files = []
            paginator = self.s3_client.get_paginator('list_objects_v2')

            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    s3_key = obj['Key']
                    size = obj['Size']
                    files.append({
                        "s3_key": s3_key,
                        "size": size,
                        "size_mb": round(size / (1024 * 1024), 2),
                        "last_modified": obj['LastModified'].isoformat(),
                        "s3_uri": f"s3://{self.bucket_name}/{s3_key}"
                    })

            logger.info(f"Found {len(files)} files in bucket {self.bucket_name} with prefix '{prefix}'")
            return files

        except Exception as e:
            error_type = type(e).__name__
            if error_type == 'ClientError':
                logger.error(f"S3 error listing files: {str(e)}")
            else:
                logger.error(f"Unexpected error listing files: {str(e)}")

            return []

    def delete_file(self, s3_key: str, delete_vectors: bool = True) -> Dict[str, Any]:
        """Delete file from S3 and optionally delete associated vectors.

        Args:
            s3_key: S3 key of file to delete
            delete_vectors: Whether to also delete vectors from vector store

        Returns:
            Dict with success status, deletion details, vector count

        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted file {s3_key} from S3")

            result = {
                "success": True,
                "s3_key": s3_key,
                "s3_deleted": True,
                "vectors_deleted": 0
            }

            if delete_vectors:
                from app.knowledge.vector_store.service import S3VectorStoreService

                source_id = self._generate_source_id(s3_key)
                vector_service = S3VectorStoreService()
                deletion_result = vector_service.delete_documents_by_source_id(source_id)

                result["vectors_deleted"] = deletion_result.get("vectors_deleted", 0)
                result["vector_deletion_success"] = deletion_result.get("success", False)
                logger.info(f"Deleted {result['vectors_deleted']} vectors for source_id {source_id}")

            return result

        except Exception as e:
            error_type = type(e).__name__
            if error_type == 'ClientError':
                logger.error(f"S3 error during deletion: {str(e)}")
            else:
                logger.error(f"Unexpected error during deletion: {str(e)}")

            return {
                "success": False,
                "error": str(e),
                "s3_key": s3_key
            }

    async def sync_file(self, s3_key: str) -> Dict[str, Any]:
        """Sync a single S3 file to the vector store.

        Args:
            s3_key: S3 key of file to sync

        Returns:
            Dict with success status, s3_key, source_id, chunk_count, file_type

        """
        try:
            content = self._read_file(s3_key)

            if not content or not content.strip():
                raise ValueError(f"File {s3_key} is empty")

            source_id = self._generate_source_id(s3_key)
            filename = Path(s3_key).name
            file_type = self._get_file_type(s3_key)

            document = Document(
                page_content=content,
                metadata={
                    "source_id": source_id,
                    "filename": filename,
                    "file_type": file_type,
                    "content_source": "internal",
                    "s3_key": s3_key,
                }
            )

            chunks = self.document_service.text_splitter.split_documents([document])
            logger.info(f"Split {s3_key} into {len(chunks)} chunks")

            for chunk in chunks:
                chunk.metadata.update(document.metadata)
                chunk.metadata["content_hash"] = hashlib.sha256(
                    chunk.page_content.encode()
                ).hexdigest()[:16]

            logger.info(f"Deleting old vectors for source_id {source_id}")
            self.vector_service.delete_documents_by_source_id(source_id)

            chunk_texts = [chunk.page_content for chunk in chunks]
            embeddings = self.document_service.generate_embeddings(chunk_texts)
            logger.info(f"Generated embeddings for {len(chunks)} chunks")

            self.vector_service.add_documents(chunks, embeddings)
            logger.info(f"Successfully synced {s3_key} to vector store")

            return {
                "success": True,
                "s3_key": s3_key,
                "source_id": source_id,
                "chunk_count": len(chunks),
                "file_type": file_type,
                "filename": filename
            }

        except Exception as e:
            error_type = type(e).__name__
            if error_type == 'ValueError':
                logger.error(f"Validation error syncing {s3_key}: {str(e)}")
            elif error_type == 'ClientError':
                logger.error(f"S3 error syncing {s3_key}: {str(e)}")
            else:
                logger.error(f"Unexpected error syncing {s3_key}: {str(e)}")

            return {
                "success": False,
                "error": str(e),
                "s3_key": s3_key
            }

    async def sync_all(self, prefix: str = "") -> Dict[str, Any]:
        """Sync all files in S3 bucket to vector store.

        Args:
            prefix: Optional prefix to filter files

        Returns:
            Dict with total, succeeded, failed counts and details list

        """
        try:
            files = self.list_files(prefix)

            if not files:
                logger.info(f"No files found to sync with prefix '{prefix}'")
                return {
                    "success": True,
                    "total": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "details": []
                }

            succeeded = 0
            failed = 0
            details = []

            for file_info in files:
                s3_key = file_info["s3_key"]
                result = await self.sync_file(s3_key)

                if result["success"]:
                    succeeded += 1
                else:
                    failed += 1

                details.append(result)

            logger.info(f"Sync complete: {succeeded} succeeded, {failed} failed out of {len(files)} total")

            return {
                "success": True,
                "total": len(files),
                "succeeded": succeeded,
                "failed": failed,
                "details": details
            }

        except Exception as e:
            logger.error(f"Error during bulk sync: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "total": 0,
                "succeeded": 0,
                "failed": 0
            }

    def _read_file(self, s3_key: str) -> str:
        """Read file content from S3.

        Args:
            s3_key: S3 key of file to read

        Returns:
            File content as string

        Raises:
            ClientError: If file cannot be read from S3
            UnicodeDecodeError: If file encoding is not UTF-8

        """
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        return content

    @staticmethod
    def _generate_source_id(s3_key: str) -> str:
        """Generate deterministic 16-character source ID from S3 key.

        Args:
            s3_key: S3 key to hash

        Returns:
            16-character hex string

        """
        return hashlib.sha256(s3_key.encode()).hexdigest()[:16]

    @staticmethod
    def _get_file_type(s3_key: str) -> str:
        """Map file extension to type classification.

        Args:
            s3_key: S3 key with file extension

        Returns:
            File type: markdown, text, json, html, csv, or text (default)

        """
        extension = Path(s3_key).suffix.lower()
        type_mapping = {
            '.md': 'markdown',
            '.markdown': 'markdown',
            '.txt': 'text',
            '.json': 'json',
            '.html': 'html',
            '.htm': 'html',
            '.csv': 'csv'
        }
        return type_mapping.get(extension, 'text')

    @staticmethod
    def _get_content_type(file_path: str) -> str:
        """Map file extension to MIME type.

        Args:
            file_path: Path to file

        Returns:
            MIME type string

        """
        content_type, _ = mimetypes.guess_type(file_path)
        return content_type or 'text/plain'
