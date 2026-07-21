from app.services.manual_session_service import (
    generate_manual_session_id,
    upload_manual_file_to_s3,
    build_manual_session_payload,
    save_manual_session_to_s3,
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

    session_payload = build_manual_session_payload(
        session_id=session_id,
        title="AWS Bedrock PDF analysis",
        instruction="Analyze this PDF and tell me the key signals for my projects and career.",
        uploaded_files=[uploaded_file_meta],
        personal_context_snapshot={},
        summary="Test summary",
        insights_for_me="Test insight for me",
        project_takeaways="Test project takeaway",
        career_takeaways="Test career takeaway",
        reflection="Test reflection",
        extracted_signals=[],
        raw_response="Test raw response",
        status="completed",
    )

    session_s3_key = save_manual_session_to_s3(
        bucket_name=S3_BUCKET,
        session_payload=session_payload,
        aws_region="us-east-1",
    )

    print("Session ID:", session_id)
    print("Uploaded source file:", uploaded_file_meta["s3_key"])
    print("Saved session json:", session_s3_key)


if __name__ == "__main__":
    main()