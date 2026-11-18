"""Tests for ref_docs.py: builds tiny .xlsx/.csv/.md/.docx files in a temp dir."""
import contextlib, io, os, tempfile, unittest, zipfile
import ref_docs

SHEET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>
<row r="2"><c r="A2"><v>1</v></c><c r="B2" t="s"><v>3</v></c><c r="C2" t="s"><v>4</v></c></row>
<row r="3"><c r="A3"><v>2</v></c><c r="B3" t="s"><v>5</v></c><c r="C3" t="inlineStr"><is><t>Chin tucks</t></is></c></row>
<row r="4"><c r="A4"><v>3</v></c><c r="C4" t="s"><v>4</v></c></row>
</sheetData></worksheet>"""
SHARED = ["#", "Head", "What Helps", "Left", "Glute strengthening", "Forward"]


def make_xlsx(path):
    sst = "".join(f"<si><t>{s}</t></si>" for s in SHARED)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml",
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="FrontalView" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr("xl/sharedStrings.xml",
                   f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{sst}</sst>')
        z.writestr("xl/worksheets/sheet1.xml", SHEET_XML)


def make_docx(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml",
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                   '<w:p><w:r><w:t>Scoliosis guidance</w:t></w:r></w:p><w:p/>'
                   '<w:p><w:r><w:t>Avoid loaded </w:t></w:r><w:r><w:t>rotation.</w:t></w:r></w:p>'
                   '</w:body></w:document>')


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ref_docs.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class RefDocsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        make_xlsx(os.path.join(d, "postural-report.xlsx"))
        make_docx(os.path.join(d, "scoliosis-notes.docx"))
        with open(os.path.join(d, "dosage.csv"), "w") as fh:
            fh.write("Phase,Sets\nAcute,1\nRemodel,3\n")
        with open(os.path.join(d, "voice.md"), "w") as fh:
            fh.write("# Tone\nWarm and plain.\n## Avoid\nJargon like lordosis.\n")
        with open(os.path.join(d, "postural-report.about.md"), "w") as fh:
            fh.write("# Postural Report\n\nPosture combinations to syndromes.\n")
        with open(os.path.join(d, "README.md"), "w") as fh:
            fh.write("# not a document\n")
        self._old = ref_docs.DOCS_DIR
        ref_docs.DOCS_DIR = d

    def tearDown(self):
        ref_docs.DOCS_DIR = self._old
        self.tmp.cleanup()

    def test_list_skips_readme_and_about_files(self):
        code, out, _ = run("list")
        self.assertEqual(code, 0)
        self.assertIn("postural-report.xlsx", out)
        self.assertIn("Posture combinations to syndromes.", out)
        self.assertIn("FrontalView: 3 rows, 3 columns", out)
        self.assertNotIn("README", out)
        self.assertNotIn("about.md", out)

    def test_xlsx_reads_shared_inline_and_missing_cells(self):
        header, rows = ref_docs.load(os.path.join(self.tmp.name, "postural-report.xlsx"))["FrontalView"]
        self.assertEqual(header, ["#", "Head", "What Helps"])
        self.assertEqual(rows, [["1", "Left", "Glute strengthening"],
                                ["2", "Forward", "Chin tucks"],
                                ["3", "", "Glute strengthening"]])

    def test_schema_shows_categories(self):
        _, out, _ = run("schema", "postural")
        self.assertIn("Head: one of Forward, Left", out)

    def test_search_requires_all_terms(self):
        _, out, _ = run("search", "postural", "glute", "left")
        self.assertIn("row 2", out)
        self.assertNotIn("row 4", out)
        self.assertIn("1 matching row(s).", out)

    def test_search_limit_reports_remaining(self):
        _, out, _ = run("search", "postural", "glute", "--limit", "1")
        self.assertIn("1 more matching rows", out)

    def test_search_all_documents(self):
        _, out, _ = run("search", "all", "rotation")
        self.assertIn("scoliosis-notes.docx › Paragraphs", out)
        self.assertIn("Avoid loaded rotation.", out)

    def test_rows_where_with_prefix_names_and_cols(self):
        _, out, _ = run("rows", "postural", "--sheet", "front", "--where", "head=left", "--cols", "what")
        self.assertIn("What Helps: Glute strengthening", out)
        self.assertNotIn("Head:", out)

    def test_values_counts(self):
        _, out, _ = run("values", "postural", "--sheet", "front", "--col", "what")
        self.assertIn("2 distinct", out)
        self.assertRegex(out, r"2\s+Glute strengthening")

    def test_csv_and_markdown(self):
        _, out, _ = run("rows", "dosage", "--sheet", "dosage", "--where", "phase=remodel")
        self.assertIn("Sets: 3", out)
        _, out, _ = run("search", "voice", "jargon")
        self.assertIn("Section: Avoid", out)

    def test_max_chars_clips(self):
        _, out, _ = run("search", "postural", "glute", "--max-chars", "5")
        self.assertIn("Glute …", out)

    def test_ambiguous_and_unknown_names_fail_cleanly(self):
        code, _, err = run("search", "o", "x")       # matches several docs
        self.assertEqual(code, 2)
        self.assertIn("several documents", err)
        code, _, err = run("rows", "postural", "--sheet", "nope", "--where", "a=b")
        self.assertEqual(code, 2)
        self.assertIn("no sheet matches", err)

    def test_empty_folder(self):
        ref_docs.DOCS_DIR = os.path.join(self.tmp.name, "missing")
        _, out, _ = run("list")
        self.assertIn("No reference documents yet", out)


class RealDocumentTest(unittest.TestCase):
    """The shipped postural report reads and has its four sheets."""

    def test_postural_report_shape(self):
        path = os.path.join(os.path.dirname(ref_docs.HERE), "reference-documents", "postural-report.xlsx")
        if not os.path.exists(path):
            self.skipTest("postural-report.xlsx not present")
        tables = ref_docs.load(path)
        self.assertEqual({k: len(v[1]) for k, v in tables.items()},
                         {"FrontalView": 729, "Saggital View": 729,
                          "Combined Posture Report": 532, "Programs": 153})


if __name__ == "__main__":
    unittest.main()
