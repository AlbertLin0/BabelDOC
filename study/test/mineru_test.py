from babeldoc._mineru import render_pdf
from pathlib import Path
from babeldoc.services.translation_service import manager
import dotenv 

dotenv.load_dotenv()


def test_render_pdf():
    res = render_pdf("test/test3.pdf", Path("test"), manager.translator)
    assert res["mono_output"] is not None
    assert res["dual_output"] is not None

if __name__ == "__main__":
    test_render_pdf()
