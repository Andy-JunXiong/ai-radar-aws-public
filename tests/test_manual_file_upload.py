from app.services.manual_session_service import (
    generate_manual_session_id,
    upload_manual_file_to_s3,
)

S3_BUCKET = "ai-radar-junxiong-data"


def main():
    session_id = generate_manual_session_id()

    local_file_path = "test_files/bedrock_report.pdf"
    file_name = "bedrock_report.pdf"

    with open(local_file_path, "rb") as f:
        file_bytes = f.read()

    uploaded_file_meta = upload_manual_file_to_s3(
        bucket_name=S3_BUCKET,
        session_id=session_id,
        file_name=file_name,
        file_bytes=file_bytes,
        aws_region="us-east-1",
    )

    print("Session ID:", session_id)
    print("Uploaded file meta:", uploaded_file_meta)


if __name__ == "__main__":
    main()