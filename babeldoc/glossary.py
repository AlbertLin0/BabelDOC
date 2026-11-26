import csv
import io
import itertools
import logging
import re
import time
from pathlib import Path

import chardet
import hyperscan
from openpyxl import load_workbook
import regex

logger = logging.getLogger(__name__)

EXCEL_LANGUAGE_COLUMNS = {
    "中文": ("zh", "中文简拼"),
    "英语": ("en", "英语简拼"),
    "西班牙语": ("es", "西班牙语简拼"),
    "泰语": ("th", "泰语简拼"),
    "德语": ("de", "德语简拼"),
    "法语": ("fr", "法语简拼"),
    "俄语": ("ru", "俄语简拼"),
    "土耳其语": ("tr", "土耳其语简拼"),
    "波兰语": ("pl", "波兰语简拼"),
}


class GlossaryEntry:
    def __init__(self, source: str, target: str, target_language: str | None = None):
        self.source = source
        self.target = target
        self.target_language = target_language

    def __repr__(self):
        return f"GlossaryEntry(source='{self.source}', target='{self.target}', target_language='{self.target_language}')"


def batched(iterable, n, *, strict=False):
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(itertools.islice(iterator, n)):
        if strict and len(batch) != n:
            raise ValueError("batched(): incomplete batch")
        yield batch


TERM_NORM_PATTERN = re.compile(r"\s+", regex.UNICODE)


class Glossary:
    def __init__(self, name: str, entries: list[GlossaryEntry]):
        self.name = name

        # Deduplicate entries based on normalized source
        unique_entries = []
        seen_normalized_sources = set()
        for entry in entries:
            normalized_source = self.normalize_source(entry.source)
            if normalized_source not in seen_normalized_sources:
                unique_entries.append(entry)
                seen_normalized_sources.add(normalized_source)
        self.entries = unique_entries

        self.normalized_lookup: dict[str, tuple[str, str]] = {}
        self.id_lookup: list[tuple[str, str]] = []
        self.hs_dbs: list[hyperscan.Database] | None = None
        self._build_regex_and_lookup()

    @staticmethod
    def normalize_source(source_term: str) -> str:
        """Normalizes a source term by lowercasing and standardizing whitespace."""
        term = source_term.lower()
        term = TERM_NORM_PATTERN.sub(
            " ", term
        )  # Replace multiple whitespace with single space
        return term.strip()

    def _build_regex_and_lookup(self):
        logger.debug(
            f"start build regex for glossary {self.name} with {len(self.entries)} entries"
        )
        """
        Builds a combined regex for all source terms and a lookup dictionary
        from normalized source terms to (original_source, original_target).
        Regex patterns are sorted by length in descending order to prioritize longer matches.
        """
        self.normalized_lookup = {}

        if not self.entries:
            self.source_terms_regex = None
            return

        self.hs_dbs = []
        hs_pattern = []
        start = time.time()
        for idx, entry in enumerate(self.entries):
            normalized_key = self.normalize_source(entry.source)
            self.normalized_lookup[normalized_key] = (entry.source, entry.target)
            self.id_lookup.append((entry.source, entry.target))

            hs_pattern.append((re.escape(entry.source).encode("utf-8"), idx))

        chunk_size = 20000
        for i, pattern_chunk in enumerate(
            batched(hs_pattern, chunk_size, strict=False)
        ):
            logger.debug(
                f"building hs_db chunk {i + 1} / {len(self.entries) // chunk_size + 1}"
            )
            expressions, ids = zip(*pattern_chunk, strict=False)

            hs_db = hyperscan.Database()
            hs_db.compile(
                expressions=expressions,
                ids=ids,
                elements=len(pattern_chunk),
                flags=hyperscan.HS_FLAG_CASELESS | hyperscan.HS_FLAG_SINGLEMATCH,
                # | hyperscan.HS_FLAG_UTF8
                # | hyperscan.HS_FLAG_UCP,
            )
            self.hs_dbs.append(hs_db)

        end = time.time()
        logger.debug(
            f"finished building regex for glossary {self.name} in {end - start:.2f} seconds"
        )
        logger.debug(
            f"build hs database for glossary {self.name} with {len(self.entries)} entries, hs_info: {self.hs_dbs[0].info()}"
        )
        if not self.hs_dbs:
            self.hs_dbs = None

    @classmethod
    def from_csv(cls, file_path: Path, target_lang_out: str) -> "Glossary":
        """
        Loads glossary entries from a CSV file.
        CSV format: source,target,tgt_lng (tgt_lng is optional)
        Filters entries based on tgt_lng matching target_lang_out.
        The glossary name is derived from the CSV filename.
        """
        glossary_name = file_path.stem
        loaded_entries: list[GlossaryEntry] = []

        # Normalize target_lang_out once for comparison
        normalized_target_lang_out = target_lang_out.lower().replace("-", "_")

        try:
            with file_path.open("rb") as f:
                content = f.read()
                encoding = chardet.detect(content)["encoding"]
                buffer = io.StringIO(content.decode(encoding))
                reader = csv.DictReader(buffer, doublequote=True)
                if not all(col in reader.fieldnames for col in ["source", "target"]):
                    raise ValueError(
                        f"CSV file {file_path} must contain 'source' and 'target' columns."
                    )

                for row in reader:
                    source = row["source"]
                    target = row["target"]
                    tgt_lng = row.get("tgt_lng", None)  # Handle optional tgt_lng

                    if tgt_lng and tgt_lng.strip():
                        normalized_entry_tgt_lng = (
                            tgt_lng.strip().lower().replace("-", "_")
                        )
                        if normalized_entry_tgt_lng != normalized_target_lang_out:
                            continue  # Skip if language doesn't match

                    loaded_entries.append(GlossaryEntry(source, target, tgt_lng))
        except FileNotFoundError:
            # Or handle as per your project's error strategy, e.g., log and return empty Glossary
            raise
        except Exception as e:
            # Or handle as per your project's error strategy
            raise ValueError(
                f"Error reading or parsing CSV file {file_path}: {e}"
            ) from e

        return cls(name=glossary_name, entries=loaded_entries)

    @classmethod
    def from_excel_by_target_language(
        cls, file_path: Path
    ) -> dict[str, "Glossary"]:
        """Loads a multilingual Excel glossary and builds one glossary per target language.

        Each language column is used as a source for every other target language.
        Chinese and English pinyin columns are included as alternate source terms.
        """
        glossary_name = file_path.stem
        workbook = load_workbook(file_path, read_only=True, data_only=True)
        try:
            worksheet = workbook.active
            rows = worksheet.iter_rows(values_only=True)
            headers = next(rows, None)
            if not headers:
                raise ValueError(f"Excel glossary {file_path} is empty.")

            header_indexes = {
                re.sub(r"\s+", "", str(header)).lower(): index
                for index, header in enumerate(headers)
                if header is not None and str(header).strip()
            }

            language_indexes: dict[str, tuple[int, int | None]] = {}
            for language_name, (language_code, alias_name) in (
                EXCEL_LANGUAGE_COLUMNS.items()
            ):
                language_index = header_indexes.get(language_name.lower())
                if language_index is None:
                    continue
                alias_index = (
                    header_indexes.get(alias_name.lower()) if alias_name else None
                )
                language_indexes[language_code] = (language_index, alias_index)

            if not language_indexes:
                raise ValueError(
                    f"Excel glossary {file_path} has no recognized language columns."
                )

            entries_by_target: dict[str, list[GlossaryEntry]] = {
                language_code: []
                for language_code in language_indexes
            }

            def cell_value(row, index: int | None) -> str:
                if index is None or index >= len(row) or row[index] is None:
                    return ""
                return str(row[index]).strip()

            for row in rows:
                for target_language, (target_index, _) in language_indexes.items():
                    target = cell_value(row, target_index)
                    if not target:
                        continue

                    for source_language, (source_index, alias_index) in (
                        language_indexes.items()
                    ):
                        if source_language == target_language:
                            continue
                        source_terms = (
                            cell_value(row, source_index),
                            cell_value(row, alias_index),
                        )
                        for source in source_terms:
                            if source:
                                entries_by_target[target_language].append(
                                    GlossaryEntry(
                                        source,
                                        target,
                                        target_language,
                                    )
                                )
        finally:
            workbook.close()

        return {
            language_code: cls(
                name=f"{glossary_name}_{language_code}",
                entries=entries,
            )
            for language_code, entries in entries_by_target.items()
            if entries
        }

    def to_csv(self) -> str:
        """Exports the glossary entries to a CSV formatted string."""
        dict_data = [
            {
                "source": x.source,
                "target": x.target,
                "tgt_lng": x.target_language if x.target_language else "",
            }
            for x in self.entries
        ]
        buffer = io.StringIO()
        dict_writer = csv.DictWriter(
            buffer, fieldnames=["source", "target", "tgt_lng"], doublequote=True
        )
        dict_writer.writeheader()
        dict_writer.writerows(dict_data)
        return buffer.getvalue()

    def __repr__(self):
        return f"Glossary(name='{self.name}', num_entries={len(self.entries)})"

    def get_active_entries_for_text(self, text: str) -> list[tuple[str, str]]:
        """Returns a list of (original_source, target_text) tuples for terms found in the given text."""
        if not self.hs_dbs or not text:
            return []

        text = TERM_NORM_PATTERN.sub(" ", text)  # Normalize whitespace in the text
        if not text:
            return []

        active_entries = []

        def on_match(
            idx: int, _from: int, _to: int, _flags: int, _context=None
        ) -> bool | None:
            active_entries.append(self.id_lookup[idx])
            return False

        for hs_db in self.hs_dbs:
            # Scan the text with the hyperscan database
            scratch = hyperscan.Scratch(hs_db)
            hs_db.scan(text.encode("utf-8"), on_match, scratch=scratch)
        return active_entries
