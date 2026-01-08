import sys
import signal
import shutil
import ocrmypdf
import shlex
import subprocess
from pathlib import Path
from multiprocessing import Process
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt


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


class DropView(QWidget):
    selected_files: list[Path] = []
    files_changed = pyqtSignal([list])

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        # 2px dashed white border
        self.setStyleSheet(
            """
            QWidget {
                border: 2px dashed white;
                background-color: #444444;
                border-radius: 10px;
            }
            """
        )

        self.label = QLabel("Drag and drop files here to convert", self)
        self.label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def update_files_label(self):
        if not self.selected_files:
            self.label.setText("Drag and drop files here to convert")
            return

        self.label.setText(
            f"""Drag and drop files here to convert
Selected files: 


{"\n".join(f.name for f in self.selected_files)}"""
        )

    def dropEvent(self, event):
        file_urls = [url.toLocalFile() for url in event.mimeData().urls()]
        file_paths = [Path(f) for f in file_urls]

        # allow only PDF files
        newly_selected_files = [
            f
            for f in file_paths
            if f.exists() and (f.is_file() and f.suffix.lower() == ".pdf")
        ]
        self.selected_files = list(set(self.selected_files + newly_selected_files))
        self.update_files_label()
        self.files_changed.emit(self.selected_files)


class MainWindow(QMainWindow):
    selected_files: list[Path] = []
    is_compressing: bool = False

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Manager")
        self.resize(720, 480)

        layout = QVBoxLayout()

        self.drop_view = DropView(self)
        self.drop_view.files_changed.connect(self.on_files_changed)
        layout.addWidget(self.drop_view)

        self.clear_button = QPushButton("Clear Files")
        self.clear_button.clicked.connect(self.clear_files)
        layout.addWidget(self.clear_button)

        self.convert_button = QPushButton("Convert and Compress PDFs")
        self.convert_button.clicked.connect(self.convert_pdfs)
        layout.addWidget(self.convert_button)

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)
        self.show()

    def set_is_compressing(self, value: bool):
        self.is_compressing = value
        self.convert_button.setEnabled(not value)
        self.convert_button.setText(
            "Converting..." if value else "Convert and Compress PDFs"
        )

    def clear_files(self):
        self.selected_files.clear()
        self.drop_view.label.setText("Drag and drop files here to convert")

    def on_files_changed(self, files: list[Path]):
        self.selected_files = files

    def convert_pdfs(self):
        if self.is_compressing or not self.selected_files:
            return

        self.set_is_compressing(True)

        for file in self.selected_files:
            convert_and_compress_pdf(file)

        self.set_is_compressing(False)
        self.clear_files()


def main() -> None:
    # quit on Ctrl-C
    signal.signal(signal.SIGINT, lambda sig, _: app.quit())

    app = QApplication(sys.argv)
    app.setApplicationName("PDF Manager")

    # call python event handlers periodically
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    ui = MainWindow()
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
