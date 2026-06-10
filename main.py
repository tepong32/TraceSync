from core.sync_service import SyncService


def main():
    service = SyncService()

    results = service.compare(
        r"C:\LOCAL",
        r"C:\SERVER",
    )

    for result in results:
        print(
            f"{result.status:<15} | {result.relative_path}"
        )


if __name__ == "__main__":
    main()