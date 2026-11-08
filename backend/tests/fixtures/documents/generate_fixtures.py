"""Generate the Sprint 5 document-readiness fixtures under tests/fixtures/documents/.

Deterministic, offline generator (stdlib + Pillow). Re-run from backend/:

    uv run python tests/fixtures/documents/generate_fixtures.py

Outputs (all small, repository-friendly):

    documents/pdf/digital-english.pdf      3-page Helvetica text PDF
    documents/pdf/digital-persian.pdf      2-page Persian PDF (embedded Vazirmatn subset)
    documents/pdf/digital-mixed.pdf        1-page mixed Persian/English PDF
    documents/pdf/digital-multicolumn.pdf  1-page two-column English PDF
    documents/pdf/scanned-english.pdf      2-page image-only PDF (OCR input)
    documents/pdf/scanned-persian.pdf      1-page image-only Persian PDF (OCR input)
    documents/docx/english.docx            DOCX with real Heading styles
    documents/docx/persian.docx            DOCX with Persian headings/paragraphs
    documents/images/scan-english.*        same scan as PNG/JPG/TIFF/BMP/WEBP
    documents/images/scan-persian.png      Persian scan image

The Persian PDFs are built glyph-by-glyph with an embedded subset of
Vazirmatn (OFL, fonts/Vazirmatn-Regular.ttf): logical Persian text is shaped
to standard Unicode presentation forms (joining rules incl. ZWNJ), laid out
RTL with per-glyph positioning, and mapped back to the original letters via a
ToUnicode CMap so text extraction returns the logical string.
"""

from __future__ import annotations

import struct
import unicodedata
import zipfile
import zlib
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

FIXTURES = Path(__file__).resolve().parent
FONT_PATH = FIXTURES / "fonts" / "Vazirmatn-Regular.ttf"

# ---------------------------------------------------------------------------
# TTF parsing / subsetting
# ---------------------------------------------------------------------------


class TTF:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.num_tables = struct.unpack(">H", data[4:6])[0]
        self.tables: dict[str, tuple[int, int]] = {}
        for i in range(self.num_tables):
            off = 12 + i * 16
            tag, _csum, offset, length = struct.unpack(">4sIII", data[off : off + 16])
            self.tables[tag.decode("latin-1")] = (offset, length)
        head = self._read("head")
        self.units_per_em = struct.unpack(">H", head[18:20])[0]
        self.index_to_loc = struct.unpack(">h", head[50:52])[0]
        maxp = self._read("maxp")
        self.num_glyphs = struct.unpack(">H", maxp[4:6])[0]
        hhea = self._read("hhea")
        self.num_hmetrics = struct.unpack(">H", hhea[34:36])[0]

    def _read(self, tag: str) -> bytes:
        offset, length = self.tables[tag]
        return self.data[offset : offset + length]

    def cmap(self) -> dict[int, int]:
        """Format-4 (3,1) subtable: codepoint -> glyph id."""
        cmap = self._read("cmap")
        n = struct.unpack(">H", cmap[2:4])[0]
        sub = None
        for i in range(n):
            pid, eid, off = struct.unpack(">HHI", cmap[4 + i * 8 : 12 + i * 8])
            fmt = struct.unpack(">H", cmap[off : off + 2])[0]
            if fmt == 4 and pid == 3 and eid == 1:
                sub = off
        seg_x2 = struct.unpack(">H", cmap[sub + 6 : sub + 8])[0]
        segs = seg_x2 // 2
        ends = struct.unpack(f">{segs}H", cmap[sub + 14 : sub + 14 + seg_x2])
        starts = struct.unpack(f">{segs}H", cmap[sub + 16 + seg_x2 : sub + 16 + 2 * seg_x2])
        deltas = struct.unpack(f">{segs}h", cmap[sub + 16 + 2 * seg_x2 : sub + 16 + 3 * seg_x2])
        rop = sub + 16 + 3 * seg_x2
        ranges = struct.unpack(f">{segs}H", cmap[rop : rop + seg_x2])
        out: dict[int, int] = {}
        for i, (s, e, d, ro) in enumerate(zip(starts, ends, deltas, ranges)):
            if s == 0xFFFF:
                continue
            for c in range(s, e + 1):
                if ro == 0:
                    gid = (c + d) & 0xFFFF
                else:
                    # glyphIndexArray offsets are relative to this segment's
                    # own entry within the array, not to the array start
                    addr = rop + i * 2 + ro + (c - s) * 2
                    gid = struct.unpack(">H", cmap[addr : addr + 2])[0]
                    if gid:
                        gid = (gid + d) & 0xFFFF
                if gid:
                    out[c] = gid
        return out

    def loca(self) -> list[int]:
        loca = self._read("loca")
        if self.index_to_loc == 0:
            return [v * 2 for v in struct.unpack(f">{self.num_glyphs + 1}H", loca)]
        return list(struct.unpack(f">{self.num_glyphs + 1}I", loca))

    def hmtx(self) -> list[int]:
        raw = self._read("hmtx")
        widths = []
        for i in range(self.num_hmetrics):
            (w,) = struct.unpack(">H", raw[i * 4 : i * 4 + 2])
            widths.append(w)
        last = widths[-1] if widths else 0
        for _ in range(self.num_hmetrics, self.num_glyphs):
            widths.append(last)
        return widths

    def component_gids(self, offset: int) -> list[int]:
        data = self._read("glyf")
        gids = []
        pos = offset + 10
        while True:
            flags, index = struct.unpack(">HH", data[pos : pos + 4])
            gids.append(index)
            pos += 4
            if flags & 0x0001:
                pos += 4
            else:
                pos += 2
            if flags & 0x0008:
                pos += 2
            elif flags & 0x0040:
                pos += 4
            elif flags & 0x0080:
                pos += 8
            if not (flags & 0x0020):
                break
        return gids


def subset_ttf(font: TTF, keep_gids: set[int]) -> bytes:
    """Subset to glyphs 0..max(keep), preserving glyph indices.

    Glyph indices are preserved so the original cmap stays valid. Composite
    glyphs are closed over; unused glyphs inside the range are emptied.
    """
    loca = font.loca()
    glyf = font._read("glyf")
    to_visit = set(keep_gids)
    while to_visit:
        gid = to_visit.pop()
        start, end = loca[gid], loca[gid + 1]
        if start == end:
            continue
        n_contours = struct.unpack(">h", glyf[start : start + 2])[0]
        if n_contours < 0:
            for comp in font.component_gids(start):
                if comp not in keep_gids:
                    keep_gids.add(comp)
                    to_visit.add(comp)

    new_num = max(keep_gids) + 1

    new_glyf = bytearray()
    new_loca = [0]
    for gid in range(new_num):
        if gid in keep_gids:
            new_glyf += glyf[loca[gid] : loca[gid + 1]]
        new_loca.append(len(new_glyf))

    raw_hmtx = font._read("hmtx")
    new_hmetrics = min(font.num_hmetrics, new_num)
    hmtx_out = bytearray()
    for i in range(new_hmetrics):
        w, lsb = struct.unpack(">Hh", raw_hmtx[i * 4 : i * 4 + 4])
        hmtx_out += struct.pack(">Hh", w, lsb)
    for i in range(new_num - new_hmetrics):
        (lsb,) = struct.unpack(">h", raw_hmtx[font.num_hmetrics * 4 + i * 2 :][0:2])
        hmtx_out += struct.pack(">h", lsb)

    head = bytearray(font._read("head"))
    struct.pack_into(">h", head, 50, 1)  # long loca
    struct.pack_into(">I", head, 8, 0)  # checkSumAdjustment, fixed below
    hhea = bytearray(font._read("hhea"))
    struct.pack_into(">H", hhea, 34, new_hmetrics)
    maxp = bytearray(font._read("maxp"))
    struct.pack_into(">H", maxp, 4, new_num)
    post = struct.pack(">IihhIIIIHH", 0x00030000, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    tables_out = {
        "OS/2": font._read("OS/2"),
        "cmap": font._read("cmap"),
        "glyf": bytes(new_glyf),
        "head": bytes(head),
        "hhea": bytes(hhea),
        "hmtx": bytes(hmtx_out),
        "loca": b"".join(struct.pack(">I", v) for v in new_loca),
        "maxp": bytes(maxp),
        "name": font._read("name"),
        "post": post,
    }

    tags = sorted(tables_out)
    num = len(tags)
    search_range, entry_selector = 1, 0
    while search_range * 2 <= num:
        search_range *= 2
        entry_selector += 1
    search_range *= 16
    header = struct.pack(">IHHHH", 0x00010000, num, search_range, entry_selector, num * 16 - search_range)

    def checksum(data: bytes) -> int:
        padded = data + b"\x00" * ((4 - len(data) % 4) % 4)
        return sum(struct.unpack(f">{len(padded)//4}I", padded)) & 0xFFFFFFFF

    directory = bytearray()
    body = bytearray()
    offset = 12 + num * 16
    for tag in tags:
        content = tables_out[tag]
        directory += struct.pack(">4sIII", tag.encode(), checksum(content), offset, len(content))
        padded = content + b"\x00" * ((4 - len(content) % 4) % 4)
        body += padded
        offset += len(padded)

    font_bytes = bytearray(header + directory + body)
    adjustment = (0xB1B0AFBA - checksum(bytes(font_bytes))) & 0xFFFFFFFF
    for i in range(num):
        off = 12 + i * 16
        if font_bytes[off : off + 4] == b"head":
            t_off = struct.unpack(">I", font_bytes[off + 8 : off + 12])[0]
            struct.pack_into(">I", font_bytes, t_off + 8, adjustment)
            break
    return bytes(font_bytes)


# ---------------------------------------------------------------------------
# Persian shaping to Unicode presentation forms
# ---------------------------------------------------------------------------

DUAL_CP = {
    0x0626, 0x0628, 0x062A, 0x062B, 0x062C, 0x0686, 0x062D, 0x062E,
    0x0633, 0x0634, 0x0635, 0x0636, 0x0637, 0x0638, 0x0639, 0x063A,
    0x0641, 0x0642, 0x06A9, 0x06AF, 0x0644, 0x0645, 0x0646, 0x0647,
    0x06CC, 0x064A,
}
# base letter -> (isolated, final, initial, medial) presentation forms
FORMS: dict[int, tuple[int, int | None, int | None, int | None]] = {
    0x0621: (0xFE80, None, None, None),
    0x0622: (0xFE81, 0xFE82, None, None),
    0x0623: (0xFE83, 0xFE84, None, None),
    0x0625: (0xFE87, 0xFE88, None, None),
    0x0627: (0xFE8D, 0xFE8E, None, None),
    0x0628: (0xFE8F, 0xFE90, 0xFE91, 0xFE92),
    0x0629: (0xFE93, 0xFE94, None, None),
    0x062A: (0xFE95, 0xFE96, 0xFE97, 0xFE98),
    0x062B: (0xFE99, 0xFE9A, 0xFE9B, 0xFE9C),
    0x062C: (0xFE9D, 0xFE9E, 0xFE9F, 0xFEA0),
    0x0686: (0xFB7A, 0xFB7B, 0xFB7C, 0xFB7D),
    0x062D: (0xFEA1, 0xFEA2, 0xFEA3, 0xFEA4),
    0x062E: (0xFEA5, 0xFEA6, 0xFEA7, 0xFEA8),
    0x062F: (0xFEA9, 0xFEAA, None, None),
    0x0630: (0xFEAB, 0xFEAC, None, None),
    0x0631: (0xFEAD, 0xFEAE, None, None),
    0x0632: (0xFEAF, 0xFEB0, None, None),
    0x0698: (0xFB8A, 0xFB8B, None, None),
    0x0633: (0xFEB1, 0xFEB2, 0xFEB3, 0xFEB4),
    0x0634: (0xFEB5, 0xFEB6, 0xFEB7, 0xFEB8),
    0x0635: (0xFEB9, 0xFEBA, 0xFEBB, 0xFEBC),
    0x0636: (0xFEBD, 0xFEBE, 0xFEBF, 0xFEC0),
    0x0637: (0xFEC1, 0xFEC2, 0xFEC3, 0xFEC4),
    0x0638: (0xFEC5, 0xFEC6, 0xFEC7, 0xFEC8),
    0x0639: (0xFEC9, 0xFECA, 0xFECB, 0xFECC),
    0x063A: (0xFECD, 0xFECE, 0xFECF, 0xFED0),
    0x0641: (0xFED1, 0xFED2, 0xFED3, 0xFED4),
    0x0642: (0xFED5, 0xFED6, 0xFED7, 0xFED8),
    0x0643: (0xFED9, 0xFEDA, 0xFEDB, 0xFEDC),
    0x06A9: (0xFB8E, 0xFB8F, 0xFB90, 0xFB91),
    0x06AF: (0xFB92, 0xFB93, 0xFB94, 0xFB95),
    0x0644: (0xFEDD, 0xFEDE, 0xFEDF, 0xFEE0),
    0x0645: (0xFEE1, 0xFEE2, 0xFEE3, 0xFEE4),
    0x0646: (0xFEE5, 0xFEE6, 0xFEE7, 0xFEE8),
    0x0647: (0xFEE9, 0xFEEA, 0xFEEB, 0xFEEC),
    0x0648: (0xFEED, 0xFEEE, None, None),
    0x0649: (0xFEEF, 0xFEF0, None, None),
    0x064A: (0xFEF1, 0xFEF2, 0xFEF3, 0xFEF4),
    0x06CC: (0xFBFC, 0xFBFD, 0xFBFE, 0xFBFF),
    0x067E: (0xFB56, 0xFB57, 0xFB58, 0xFB59),
    0x0624: (0xFE85, 0xFE86, None, None),
    0x0626: (0xFE89, 0xFE8A, 0xFE8B, 0xFE8C),
}


def shape_arabic(text: str) -> list[tuple[int, int]]:
    """Logical Arabic-script string -> [(presentation codepoint, original)].

    ZWNJ is kept as its own zero-width glyph (it breaks joining and survives
    in the text layer). Non-Arabic characters pass through unchanged.
    """
    chars = list(text)
    out: list[tuple[int, int]] = []

    def joins_right(idx: int) -> bool:
        """Does the letter at idx connect to the previous one?

        Only dual-joining letters connect forward, so walk back (marks are
        transparent) and require a dual-joining letter; ZWNJ blocks.
        """
        j = idx - 1
        while j >= 0:
            cp = ord(chars[j])
            if cp == 0x200C:
                return False
            if cp in FORMS:
                return cp in DUAL_CP
            if unicodedata.category(chr(cp)).startswith("M"):
                j -= 1
                continue
            return False
        return False

    def joins_left(idx: int) -> bool:
        """Does the letter at idx connect to the following one?"""
        j = idx + 1
        while j < len(chars):
            cp = ord(chars[j])
            if cp == 0x200C:
                return False
            if cp in FORMS:
                return True  # dual- and right-joining letters both connect backward
            if unicodedata.category(chr(cp)).startswith("M"):
                j += 1
                continue
            return False
        return False

    for i, ch in enumerate(chars):
        cp = ord(ch)
        if cp == 0x200C:
            out.append((0x200C, cp))
            continue
        if cp in FORMS:
            isol, fina, init, medi = FORMS[cp]
            prev_joins = joins_right(i) and cp in DUAL_CP
            next_joins = joins_left(i) and cp in DUAL_CP
            if prev_joins and next_joins and medi is not None:
                out.append((medi, cp))
            elif prev_joins and fina is not None:
                out.append((fina, cp))
            elif next_joins and init is not None:
                out.append((init, cp))
            else:
                out.append((isol, cp))
        else:
            out.append((cp, cp))
    return out


# ---------------------------------------------------------------------------
# PDF writer (Type0/CIDFontType2 with embedded subset, or standard fonts)
# ---------------------------------------------------------------------------

SPACE_GID = 592  # Vazirmatn space glyph


def _is_arabic_cp(cp: int) -> bool:
    if 0x0660 <= cp <= 0x0669 or 0x06F0 <= cp <= 0x06F9:
        return False  # digits run LTR even inside RTL text
    return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF


def segment_runs(text: str) -> list[tuple[str, str]]:
    """Split text into ('rtl'|'ltr') runs; neutrals attach to the current run."""
    runs: list[tuple[str, str]] = []
    cur_dir = "rtl"
    cur: list[str] = []
    for ch in text:
        cp = ord(ch)
        if _is_arabic_cp(cp):
            d = "rtl"
        elif ch == " " or cp == 0x200C:
            d = cur_dir
        else:
            d = "ltr"
        if d == cur_dir or not cur:
            cur_dir = d
            cur.append(ch)
        else:
            runs.append((cur_dir, "".join(cur)))
            cur_dir = d
            cur = [ch]
    if cur:
        runs.append((cur_dir, "".join(cur)))
    return runs


class FontResource:
    def __init__(self, ttf_path: Path) -> None:
        self.ttf = TTF(ttf_path.read_bytes())
        self.cmap = self.ttf.cmap()
        self.units = self.ttf.units_per_em
        self._widths = self.ttf.hmtx()
        self.used: dict[int, int] = {}  # gid -> original codepoint (ToUnicode)

    def gid(self, cp: int) -> int | None:
        if cp == 0x20:
            return SPACE_GID
        return self.cmap.get(cp)

    def width_pdf(self, gid: int, size: float) -> float:
        return self._widths[gid] * size / self.units


class PageContent:
    def __init__(self, width: float = 595, height: float = 842) -> None:
        self.width = width
        self.height = height
        self.ops: list[str] = []

    def line_rtl(self, font: FontResource, text: str, x_right: float, y: float, size: float) -> None:
        """One line, base direction RTL, glyph stream in logical order."""
        shaped: list[tuple[str, list[tuple[int, int]]]] = []
        for direction, run_text in segment_runs(text):
            if direction == "rtl":
                shaped.append((direction, shape_arabic(run_text)))
            else:
                shaped.append((direction, [(ord(c), ord(c)) for c in run_text]))
        cursor = x_right
        for direction, glyphs in shaped:
            if direction == "rtl":
                pos = cursor
                placed = []
                for form_cp, original in glyphs:
                    gid = font.gid(form_cp)
                    if gid is None:
                        continue
                    gw = font.width_pdf(gid, size)
                    font.used.setdefault(gid, original)
                    placed.append((pos - gw, gid))
                    pos -= gw
                for x, gid in placed:  # logical order, positioned right-to-left
                    self.ops.append(f"BT /F0 {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm <{gid:04X}> Tj ET")
            else:
                pos = cursor - sum(
                    font.width_pdf(font.gid(cp), size)
                    for cp, _ in glyphs
                    if font.gid(cp) is not None
                )
                for cp, _ in glyphs:
                    gid = font.gid(cp)
                    if gid is None:
                        continue
                    gw = font.width_pdf(gid, size)
                    font.used.setdefault(gid, cp)
                    self.ops.append(f"BT /F0 {size:.2f} Tf 1 0 0 1 {pos:.2f} {y:.2f} Tm <{gid:04X}> Tj ET")
                    pos += gw
            cursor -= sum(
                font.width_pdf(font.gid(cp), size)
                for cp, _ in glyphs
                if font.gid(cp) is not None
            )

    def line_ltr(self, text: str, x: float, y: float, size: float, font_name: str = "F1") -> None:
        self.ops.append(f"BT /{font_name} {size:.2f} Tf {x:.2f} {y:.2f} Td ({_pdf_escape(text)}) Tj ET")

    def jpeg_image(self, jpeg_bytes: bytes, width: int, height: int) -> None:
        self.ops.append(f"q {self.width:.0f} 0 0 {self.height:.0f} 0 0 cm /Im0 Do Q")
        self.jpeg = (jpeg_bytes, width, height)  # type: ignore[attr-defined]


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf(pages: list[PageContent], out: Path, font: FontResource | None = None) -> None:
    """Assemble a multi-page PDF.

    With a FontResource, one Type0 font (F0, embedded subset) serves all
    pages; otherwise pages must reference the standard font F1 (Helvetica).
    """
    obj_list: list[bytes] = []

    def obj(body: bytes) -> int:
        obj_list.append(body)
        return len(obj_list)

    type0_id = 0
    if font is not None:
        subset = subset_ttf(font.ttf, set(font.used) | {0})
        w_entries = " ".join(
            f"{gid} [{font._widths[gid] * 1000 / font.units:.0f}]" for gid in sorted(font.used)
        )
        hhea = font.ttf._read("hhea")
        ascent = struct.unpack(">h", hhea[4:6])[0] * 1000 / font.units
        descent = struct.unpack(">h", hhea[6:8])[0] * 1000 / font.units

        ff = obj(
            b"<< /Length1 %d /Length %d >>\nstream\n" % (len(subset), len(subset))
            + subset
            + b"\nendstream"
        )
        bf = "\n".join(
            f"<{gid:04X}> <{chr(original).encode('utf-16-be').hex().upper()}>"
            for gid, original in sorted(font.used.items())
        )
        cmap_body = (
            "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
            f"{len(font.used)} beginbfchar\n{bf}\nendbfchar\n"
            "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
        ).encode("latin-1")
        tu = obj(b"<< /Length %d >>\nstream\n" % len(cmap_body) + cmap_body + b"\nendstream")
        desc = obj(
            f"<< /Type /FontDescriptor /FontName /Vazirmatn /Flags 4 "
            f"/FontBBox [0 {descent:.0f} 1000 {ascent:.0f}] /ItalicAngle 0 "
            f"/Ascent {ascent:.0f} /Descent {descent:.0f} /CapHeight {ascent:.0f} "
            f"/StemV 40 /FontFile2 {ff} 0 R >>".encode()
        )
        dfont = obj(
            f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Vazirmatn "
            f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
            f"/FontDescriptor {desc} 0 R /DW 1000 /W [{w_entries}] /CIDToGIDMap /Identity >>".encode()
        )
        type0_id = obj(
            f"<< /Type /Font /Subtype /Type0 /BaseFont /Vazirmatn "
            f"/Encoding /Identity-H /DescendantFonts [{dfont} 0 R] /ToUnicode {tu} 0 R >>".encode()
        )
    else:
        # standard-font pages (F1/Helvetica content streams) need no embedding
        type0_id = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    content_ids: list[int] = []
    for page in pages:
        stream = "\n".join(page.ops).encode("latin-1")
        comp = zlib.compress(stream)
        content_ids.append(
            obj(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(comp) + comp + b"\nendstream")
        )

    image_ids: list[int | None] = []
    for page in pages:
        if hasattr(page, "jpeg"):
            jpeg, w, h = page.jpeg  # type: ignore[attr-defined]
            im = obj(
                b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                b"/Length %d >>\nstream\n" % (w, h, len(jpeg))
                + jpeg
                + b"\nendstream"
            )
            image_ids.append(im)
        else:
            image_ids.append(None)

    pages_num = len(obj_list) + len(pages) + 1
    page_ids = []
    for i, page in enumerate(pages):
        im_id = image_ids[i]
        xobj_res = f" /XObject << /Im0 {im_id} 0 R >>" if im_id is not None else ""
        if font is not None:
            resources = f"<< /Font << /F0 {type0_id} 0 R >>{xobj_res} >>"
        else:
            resources = f"<< /Font << /F1 {type0_id} 0 R >>{xobj_res} >>"
        page_ids.append(
            obj(
                f"<< /Type /Page /Parent {pages_num} 0 R "
                f"/MediaBox [0 0 {page.width:.0f} {page.height:.0f}] "
                f"/Resources {resources} /Contents {content_ids[i]} 0 R >>".encode()
            )
        )
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_id = obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    assert pages_id == pages_num
    catalog_id = obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    data = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(obj_list, start=1):
        offsets.append(len(data))
        data += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 %d\n" % (len(obj_list) + 1)
    data += b"0000000000 65535 f \n"
    for off in offsets:
        data += b"%010d 00000 n \n" % off
    data += (
        b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(obj_list) + 1, catalog_id, xref)
    )
    out.write_bytes(bytes(data))


# ---------------------------------------------------------------------------
# Scanned-page rendering (PIL) and DOCX builder
# ---------------------------------------------------------------------------


def render_scan_image(
    lines: list[tuple[str, str]],  # (text, script) pairs
    out_path: Path,
    width: int = 1240,
    height: int = 1754,
) -> None:
    """Render text lines onto a white page image (a 'scan')."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = 120
    for text, script in lines:
        if script == "fa":
            font = ImageFont.truetype(str(FONT_PATH), 44)
            shaped_visual = "".join(
                chr(cp) for cp, _ in reversed(shape_arabic(text))
            )
            draw.text((width - 120, y), shaped_visual, font=font, fill="black", anchor="ra")
        else:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 48)
            draw.text((120, y), text, font=font, fill="black")
        y += 110
    img.save(out_path)


def write_docx(
    out_path: Path,
    blocks: list[tuple[str, str, str]],  # (kind, text, style) kind: heading|para
) -> None:
    """Minimal OOXML DOCX with real Heading styles docling recognizes."""
    paragraphs = []
    for kind, text, _style in blocks:
        if kind == "heading":
            paragraphs.append(
                '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'
            )
        else:
            paragraphs.append(
                '<w:p><w:r><w:t xml:space="preserve">{}</w:t></w:r></w:p>'.format(
                    escape(text)
                )
            )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(paragraphs)}"
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>'
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults>'
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>'
        '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/></w:style></w:styles>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        zf.writestr("word/styles.xml", styles)
        zf.writestr("word/document.xml", document)


# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------


def pdf_digital_english(out: Path) -> None:
    pages = [
        [
            ("Quarterly Financial Report", 22, 750),
            ("Fiscal year 2024 revenue grew twelve percent", 14, 700),
            ("The board approved the operating budget in March.", 14, 660),
        ],
        [
            ("Risk Factors", 18, 750),
            ("Market conditions may reduce future revenue growth.", 14, 700),
            ("Regulatory changes remain the primary external risk.", 14, 660),
        ],
        [
            ("Operational Highlights", 18, 750),
            ("Microsoft Cloud revenue exceeded internal targets.", 14, 700),
        ],
    ]
    pages_out = []
    for blocks in pages:
        page = PageContent()
        for text, size, y in blocks:
            page.line_ltr(text, 60, y, size)
        pages_out.append(page)
    build_pdf(pages_out, out)


def pdf_digital_persian(out: Path) -> None:
    font = FontResource(FONT_PATH)
    p1 = PageContent()
    p1.line_rtl(font, "گزارش مالی سالانه", 535, 760, 20)
    p1.line_rtl(font, "شرکت\u200cهای ایرانی در سال ۱۴۰۳ رشد کردند.", 535, 700, 14)
    p1.line_rtl(font, "درآمد نسبت به سال ١٤٠٢ افزایش یافت.", 535, 660, 14)
    p1.line_rtl(font, "پروژه OpenAI و مدل\u200cهای AI در بازار 10-K آمده\u200cاند.", 535, 620, 14)
    p2 = PageContent()
    p2.line_rtl(font, "ریسک‌های بازار", 535, 760, 18)
    p2.line_rtl(font, "نوسان ارز می‌تواند سود را کاهش دهد.", 535, 700, 14)
    p2.line_rtl(font, "میزان ریسک‌های عملیاتی در گزارش 2024 ذکر شد.", 535, 660, 14)
    build_pdf([p1, p2], out, font=font)


def pdf_digital_mixed(out: Path) -> None:
    font = FontResource(FONT_PATH)
    page = PageContent()
    page.line_rtl(font, "گزارش 10-K شرکت MSFT برای سال 2024", 535, 760, 15)
    page.line_rtl(font, "درآمد Azure رشد کرد و AI revenue دو برابر شد.", 535, 710, 14)
    page.line_rtl(font, "ریسک اصلی: نوسان نرخ ارز و market competition.", 535, 660, 14)
    build_pdf([page], out, font=font)


def pdf_digital_multicolumn(out: Path) -> None:
    page = PageContent()
    left = [
        "ALPHA-01 column paragraph one.",
        "ALPHA-02 column paragraph two.",
        "ALPHA-03 column paragraph three.",
        "ALPHA-04 column paragraph four.",
        "ALPHA-05 column paragraph five.",
    ]
    right = [
        "BETA-01 right column item one.",
        "BETA-02 right column item two.",
        "BETA-03 right column item three.",
        "BETA-04 right column item four.",
        "BETA-05 right column item five.",
    ]
    y = 740
    for text in left:
        page.line_ltr(text, 60, y, 12)
        y -= 60
    y = 740
    for text in right:
        page.line_ltr(text, 330, y, 12)
        y -= 60
    build_pdf([page], out)


def pdf_scanned(out_stem: Path, pages_lines: list[list[tuple[str, str]]]) -> None:
    pages_out = []
    for lines in pages_lines:
        page = PageContent()
        tmp_png = out_stem.parent / f".scan-tmp-{abs(hash(tuple(lines))) % 99999}.png"
        render_scan_image(lines, tmp_png)
        img = Image.open(tmp_png).convert("RGB")
        tmp_jpeg = tmp_png.with_suffix(".jpg")
        img.save(tmp_jpeg, "JPEG", quality=85)
        page.jpeg = (tmp_jpeg.read_bytes(), img.width, img.height)
        page.ops.append(f"q {page.width:.0f} 0 0 {page.height:.0f} 0 0 cm /Im0 Do Q")
        tmp_png.unlink()
        tmp_jpeg.unlink()
        pages_out.append(page)
    build_pdf(pages_out, out_stem.with_suffix(".pdf"))


def images_scan(out_stem: Path, lines: list[tuple[str, str]], formats: list[str]) -> None:
    tmp = out_stem.parent / f".img-tmp-{abs(hash(tuple(lines))) % 99999}.png"
    render_scan_image(lines, tmp)
    img = Image.open(tmp)
    for fmt in formats:
        target = out_stem.with_suffix(f".{fmt}")
        img.save(target, fmt.upper() if fmt != "jpg" else "JPEG")
    tmp.unlink()


def main() -> None:
    pdf_digital_english(FIXTURES / "pdf" / "digital-english.pdf")
    pdf_digital_persian(FIXTURES / "pdf" / "digital-persian.pdf")
    pdf_digital_mixed(FIXTURES / "pdf" / "digital-mixed.pdf")
    pdf_digital_multicolumn(FIXTURES / "pdf" / "digital-multicolumn.pdf")

    pdf_scanned(
        FIXTURES / "pdf" / "scanned-english",
        [
            [
                ("INVOICE TOTAL 1250 DOLLARS", "en"),
                ("DUE DATE 2024-05-30", "en"),
                ("ACCOUNT RISK REVIEW", "en"),
            ],
            [
                ("FISCAL YEAR 2024 REPORT", "en"),
                ("REVENUE GREW TWELVE PERCENT", "en"),
            ],
        ],
    )
    pdf_scanned(
        FIXTURES / "pdf" / "scanned-persian",
        [
            [
                ("گزارش مالی شرکت", "fa"),
                ("درآمد سال ۱۴۰۳ رشد کرد", "fa"),
            ]
        ],
    )

    write_docx(
        FIXTURES / "docx" / "english.docx",
        [
            ("heading", "Annual Report", "Heading1"),
            ("para", "This document describes the fiscal year 2024 results.", "Normal"),
            ("heading", "Financial Position", "Heading1"),
            ("para", "Revenue increased while operating costs stayed flat.", "Normal"),
        ],
    )
    write_docx(
        FIXTURES / "docx" / "persian.docx",
        [
            ("heading", "گزارش سالانه", "Heading1"),
            ("para", "شرکت\u200cهای ایرانی در سال ۱۴۰۳ رشد کردند.", "Normal"),
            ("heading", "ریسک‌های بازار", "Heading1"),
            ("para", "پروژه‌های OpenAI و AI در گزارش آمده\u200cاند.", "Normal"),
        ],
    )

    scan_lines = [
        ("QUARTERLY REVENUE REPORT", "en"),
        ("TOTAL 3400 UNITS SOLD", "en"),
        ("RISK FACTORS REVIEWED", "en"),
    ]
    images_scan(FIXTURES / "images" / "scan-english", scan_lines, ["png", "jpg", "tiff", "bmp", "webp"])
    images_scan(
        FIXTURES / "images" / "scan-persian",
        [("گزارش مالی سال ۱۴۰۳", "fa")],
        ["png"],
    )

    print("fixtures written to", FIXTURES)


if __name__ == "__main__":
    main()
