#!/usr/bin/env python3
"""
Bulk student enrollment script from a photo directory.
Supports two folder layouts:
1. Subfolder per student:
   data/incoming_photos/
     ├── John_Doe_20230001/
     │     ├── photo1.jpg
     │     └── photo2.jpg
     └── Mary_Smith_20230002/
           └── photo.png

2. Loose image files named with student name and ID:
   data/incoming_photos/
     ├── John_Doe_20230001.jpg
     └── Mary_Smith_20230002.png

Usage:
  python scripts/bulk_enroll.py --folder data/incoming_photos --group "Group A"
"""
import sys
import re
import argparse
from pathlib import Path

# Add project root and backend directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from scripts.enroll_student import enroll_student

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

def parse_name_and_number(identifier: str) -> tuple[str, str]:
    """
    Parses strings like 'John_Doe_20230001' or '20230001_John_Doe'.
    """
    parts = re.split(r"[_ -]+", identifier.strip())
    
    number = None
    name_parts = []
    
    for part in parts:
        if re.match(r"^\d{4,}$", part) and number is None:
            number = part
        elif re.match(r"^[A-Za-z0-9]{6,}$", part) and any(c.isdigit() for c in part) and number is None:
            number = part
        else:
            name_parts.append(part)
            
    if not number:
        number = name_parts.pop() if len(name_parts) > 1 else "NO_ID"
        
    name = " ".join(name_parts) if name_parts else identifier
    return name, number

def process_bulk_folder(folder_path: Path, group_name: str, course_code: str):
    if not folder_path.exists():
        print(f"[ERROR] Target folder does not exist: {folder_path}")
        return

    print(f"=== Processing Bulk Enrollment from: {folder_path} ===")
    
    # 1. Detect subdirectories
    subdirs = [d for d in folder_path.iterdir() if d.is_dir()]
    processed_count = 0
    
    if subdirs:
        print(f"Found {len(subdirs)} student subdirectories.")
        for d in sorted(subdirs):
            photos = [p for p in d.iterdir() if p.suffix.lower() in VALID_EXTENSIONS]
            if not photos:
                continue
            name, number = parse_name_and_number(d.name)
            print(f"\n--- Processing: {name} (ID: {number}) with {len(photos)} photo(s) ---")
            enroll_student(
                name=name,
                student_number=number,
                photo_paths=[str(p) for p in photos],
                group_name=group_name,
                course_code=course_code
            )
            processed_count += 1
    
    # 2. Detect loose image files in the root folder
    loose_files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS]
    if loose_files:
        print(f"\nFound {len(loose_files)} loose image files.")
        for f in sorted(loose_files):
            name, number = parse_name_and_number(f.stem)
            print(f"\n--- Processing: {name} (ID: {number}) ---")
            enroll_student(
                name=name,
                student_number=number,
                photo_paths=[str(f)],
                group_name=group_name,
                course_code=course_code
            )
            processed_count += 1
            
    print(f"\n=== Bulk enrollment completed. Total students processed: {processed_count} ===")

def main():
    parser = argparse.ArgumentParser(description="Bulk student face enrollment from directory.")
    parser.add_argument("--folder", type=str, default="data/incoming_photos", help="Path to photos directory")
    parser.add_argument("--group", type=str, default="Group A", help="Academic group name")
    parser.add_argument("--course", type=str, default="COURSE-101", help="Course code")

    args = parser.parse_args()
    folder_path = Path(args.folder).resolve()
    process_bulk_folder(folder_path, group_name=args.group, course_code=args.course)

if __name__ == "__main__":
    main()
