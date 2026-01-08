import sys
import signal
import shutil
import ocrmypdf
import shlex
import subprocess
from pathlib import Path
from multiprocessing import Process
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton
from PyQt6.QtCore import QTimer


def run_ocr(input_file: Path, output_file: Path) -> None:
    ocrmypdf.ocr(
        input_file=str(input_file),
        output_file=str(output_file),
        language="deu",
        rotate_pages=True,
        deskew=True,
        output_type="pdf",
        force_ocr=True,
    )


def convert_and_compress_pdf(file: Path) -> bool:
    file = file.resolve()
    ocr_file = file.with_name(f"{file.stem}_ocr{file.suffix}")
    compressed_file = file.with_name(f"{file.stem}_compressed{file.suffix}")

    GS_OPTIONS = "-sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/default -dNOPAUSE -dBATCH -dDetectDuplicateImages -dCompressFonts=true -r300"

    try:
        p = Process(target=run_ocr, args=(file, ocr_file))
        p.start()
        p.join()
    except Exception as e:
        print(f"Error converting {file}: {e}")
        return False

    try:
        cmd = shlex.split(
            f"gs {GS_OPTIONS} -sOutputFile='{compressed_file}' '{ocr_file}'"
        )
        subprocess.run(cmd, check=True)
    except Exception as e:
        compressed_file.unlink(missing_ok=True)
        print(f"Error compressing {ocr_file}: {e}")
        return False

    ocr_file.unlink(missing_ok=True)
    shutil.move(compressed_file, file)
    print(f"Converted: {file}")
    return True


class MainWindow(QMainWindow):
    selected_files: list[str] = []

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Manager")
        self.resize(720, 480)

        # Central text with 1px dotted border to indicate drop area
        label = QLabel("Drop PDF files here", self)
        label.setStyleSheet(
            """
            font-size: 24px;
            qproperty-alignment: 'AlignCenter';
        """
        )
        self.setCentralWidget(label)

        convert_button = QPushButton("Convert", self)
        convert_button.clicked.connect(self.convert_pdfs)
        convert_button.setGeometry(10, 10, 100, 30)

        self.setAcceptDrops(True)
        self.show()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.selected_files.extend(files)

    def convert_pdfs(self):
        for file in self.selected_files:
            convert_and_compress_pdf(Path(file))

        self.selected_files.clear()


def main() -> None:
    # quit on Ctrl-C
    signal.signal(signal.SIGINT, lambda sig, _: app.quit())

    app = QApplication(sys.argv)

    # call python event handlers periodically
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    ui = MainWindow()
    ui.show()
    sys.exit(app.exec())
