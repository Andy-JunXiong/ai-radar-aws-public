from app.services.manual_session_service import (
    build_manual_session_payload,
    update_manual_latest_sessions,
)

S3_BUCKET = "ai-radar-junxiong-data"


def main():
    session_payload = build_manual_session_payload(
        session_id="manual_test_latest_001",
        title="Manual Vision Analysis",
        instruction="Test latest sessions",
        uploaded_files=[
            {
                "file_name": "upload_1.jpg",
                "file_type": "jpg",
                "s3_key": "manual_uploads/manual_test_latest_001/source_files/upload_1.jpg"
            }
        ],
        summary="This is a test summary for latest session index.",
        insights_for_me="",
        project_takeaways="",
        career_takeaways="",
        reflection="",
        extracted_signals=[],
        raw_response="",
        status="completed",
    )

    latest_key = update_manual_latest_sessions(
        bucket_name=S3_BUCKET,
        session_payload=session_payload,
        aws_region="us-east-1",
        max_sessions=20,
    )

    print("Updated latest index:", latest_key)


if __name__ == "__main__":
    main()