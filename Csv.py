import csv
import sys


def csv_to_markdown(csv_path: str) -> str:
    with open(csv_path, newline="", encoding="utf-8-sig") as file:
        rows = list(csv.reader(file))

    if not rows:
        return ""

    column_count = max(len(row) for row in rows)
    rows = [row + [""] * (column_count - len(row)) for row in rows]

    def escape(value: str) -> str:
        return value.strip().replace("|", r"\|").replace("\n", "<br>")

    header = rows[0]
    body = rows[1:]

    lines = [
        "| " + " | ".join(map(escape, header)) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]

    lines.extend(
        "| " + " | ".join(map(escape, row)) + " |"
        for row in body
    )

    return "\n".join(lines)


if __name__ == "__main__":
    markdown = csv_to_markdown(sys.argv[1])

    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as file:
            file.write(markdown + "\n")
    else:
        print(markdown)
