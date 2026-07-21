from app.services.manual_session_service import (
    build_manual_session_payload,
    save_manual_session_to_s3,
)

S3_BUCKET = "ai-radar-junxiong-data"


def main():
    uploaded_files = [
        {
            "file_name": "bedrock_report.pdf",
            "file_type": "pdf",
            "s3_key": "manual_uploads/manual_20260325_103500/source_files/bedrock_report.pdf"
        }
    ]

    session_payload = build_manual_session_payload(
        title="AWS Bedrock PDF analysis",
        instruction="Analyze this PDF and tell me the key signals for my projects and career.",
        uploaded_files=uploaded_files,
        personal_context_snapshot={},
        summary="This is a test summary.",
        insights_for_me="This is a test insight for me.",
        project_takeaways="This is a test project takeaway.",
        career_takeaways="This is a test career takeaway.",
        reflection="This is a test reflection.",
        extracted_signals=[],
        raw_response="This is a raw test response.",
        status="completed",
    )

    s3_key = save_manual_session_to_s3(
        bucket_name=S3_BUCKET,
        session_payload=session_payload,
        aws_region="us-east-1",
    )

    print("Saved to S3:", s3_key)
    print("Session ID:", session_payload["session_id"])


if __name__ == "__main__":
    main()