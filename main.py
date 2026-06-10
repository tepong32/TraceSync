from core.scanner import scan_folder
from core.comparer import compare_folders


def main():
    local_files = scan_folder(r"C:\Users\TEMP.MARIZ\Desktop\GSO inv")

    server_files = scan_folder(r"C:\Users\TEMP.MARIZ\Desktop\SCAN")

    results = compare_folders(
        local_files,
        server_files,
    )

    for result in results:
        print(
            f"{result.status:<15} | {result.relative_path}"
        )


if __name__ == "__main__":
    main()