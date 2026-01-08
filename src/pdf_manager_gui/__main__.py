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
from PyQt6.QtCore import (
    QTimer,
    Qt,
    QThreadPool,
    QRunnable,
    pyqtSlot,
    pyqtSignal,
    QObject,
)


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


class PDFResult(QObject):
    finished = pyqtSignal([Path, bool])


class PDF(QRunnable):
    signals: PDFResult

    def __init__(self, file: Path):
        super().__init__()
        self.file = file.resolve()
        self.signals = PDFResult()

    @pyqtSlot()
    def run(self) -> None:
        ocr_file = self.file.with_name(f"{self.file.stem}_ocr{self.file.suffix}")
        compressed_file = self.file.with_name(
            f"{self.file.stem}_compressed{self.file.suffix}"
        )

        GS_OPTIONS = "-sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/default -dNOPAUSE -dBATCH -dDetectDuplicateImages -dCompressFonts=true -r300"

        try:
            p = Process(target=run_ocr, args=(self.file, ocr_file))
            p.start()
            p.join()
        except Exception as e:
            print(f"Error converting {self.file}: {e}")
            self.signals.finished.emit(self.file, False)
            return

        try:
            cmd = shlex.split(
                f"gs {GS_OPTIONS} -sOutputFile='{compressed_file}' '{ocr_file}'"
            )
            subprocess.run(cmd, check=True)
        except Exception as e:
            compressed_file.unlink(missing_ok=True)
            print(f"Error compressing {ocr_file}: {e}")
            self.signals.finished.emit(self.file, False)
            return

        ocr_file.unlink(missing_ok=True)
        shutil.move(compressed_file, self.file)
        self.signals.finished.emit(self.file, True)


class DropView(QWidget):
    selected_files: list[Path] = []
    NO_FILES_TEXT = "Drag and drop files here to convert"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        # 2px dashed white border
        self.setStyleSheet(
            """
            QWidget {
                border: 2px dashed white;
                border-radius: 10px;
            }
            """
        )

        self.label = QLabel(self.NO_FILES_TEXT, self)
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

    def clear_files(self):
        self.selected_files = []
        self.update_files_label()

    def update_files_label(self):
        if not self.selected_files:
            self.label.setText(self.NO_FILES_TEXT)
            return

        file_names = "\n".join(f.name for f in self.selected_files)
        self.label.setText(
            f"Drag and drop files here to convert\nSelected files:\n\n{file_names}"
        )


class MainWindow(QMainWindow):
    is_compressing: bool = False
    pool: QThreadPool

    def __init__(self):
        super().__init__()
        self.pool = QThreadPool()

        self.setWindowTitle("PDF Manager")
        self.resize(720, 480)

        layout = QVBoxLayout()

        self.drop_view = DropView(self)
        layout.addWidget(self.drop_view)

        self.clear_button = QPushButton("Clear Files", self)
        self.clear_button.clicked.connect(self.drop_view.clear_files)
        layout.addWidget(self.clear_button)

        self.convert_button = QPushButton("Convert and Compress PDFs", self)
        self.convert_button.clicked.connect(self.convert_pdfs)
        layout.addWidget(self.convert_button)

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)
        self.show()

    def on_file_finished(self, file: Path, success: bool):
        if success:
            print(f"Finished processing {file}")

        self.drop_view.selected_files.remove(file)
        self.drop_view.update_files_label()
        if not self.drop_view.selected_files:
            self.set_is_compressing(False)

    def set_is_compressing(self, value: bool):
        self.is_compressing = value
        if value:
            self.convert_button.setText("Converting...")
        else:
            self.convert_button.setText("Convert and Compress PDFs")

    def convert_pdfs(self):
        if self.is_compressing or not self.drop_view.selected_files:
            return

        self.set_is_compressing(True)

        for file in self.drop_view.selected_files:
            pdf = PDF(file)
            pdf.signals.finished.connect(self.on_file_finished)
            self.pool.start(pdf)


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
