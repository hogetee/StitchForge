import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof",type=Path,help="Export the three DST proof designs")
    parser.add_argument("--smoke-test",action="store_true",help="Render desktop and exit")
    parser.add_argument("--project",type=Path,help="Open an editable .stitchforge layer project")
    parser.add_argument("--digitize",action="store_true",help="Generate a stitch preview after opening --project")
    parser.add_argument("--snapshot",type=Path,default=Path('examples/desktop-preview.png'),help="Screenshot destination for --smoke-test")
    args = parser.parse_args()
    if args.digitize and not args.project:
        parser.error('--digitize requires --project')
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
    if args.project:
        window.restore_project(args.project)
        if args.digitize:
            QTimer.singleShot(0,window.generate)
    if args.smoke_test:
        def finish():
            if window.thread is not None:
                QTimer.singleShot(200,finish)
                return
            args.snapshot.parent.mkdir(parents=True,exist_ok=True)
            window.grab().save(str(args.snapshot))
            app.quit()
        QTimer.singleShot(500,finish)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
