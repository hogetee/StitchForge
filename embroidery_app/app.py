import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof",type=Path,help="Export the three DST proof designs")
    parser.add_argument("--smoke-test",action="store_true",help="Render desktop and exit")
    args = parser.parse_args()
    if args.proof:
        from embroidery_app.examples import proof_design
        from embroidery_app.exporters.dst import export_dst
        args.proof.mkdir(parents=True,exist_ok=True)
        for kind in ("square","circle","multicolor"):
            print(kind,json.dumps(export_dst(proof_design(kind),args.proof/f"{kind}.dst")))
        return
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from embroidery_app.ui.main_window import MainWindow
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    if args.smoke_test:
        def finish():
            Path("examples").mkdir(exist_ok=True)
            window.grab().save("examples/desktop-preview.png")
            app.quit()
        QTimer.singleShot(500,finish)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
