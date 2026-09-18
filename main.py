import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, ttk
from PIL import Image, ImageTk, ImageOps, ImageDraw
from rembg import remove, new_session


APP_TITLE = "Passport Photo Maker"
DEFAULT_W_MM = 35
DEFAULT_H_MM = 45
DEFAULT_DPI = 300
A4_W_IN = 8.27
A4_H_IN = 11.69


def mm_to_px(mm, dpi=DEFAULT_DPI):
    return round(mm / 25.4 * dpi)


def fit_crop(image, target_ratio):
    width, height = image.size
    ratio = width / height
    if ratio > target_ratio:
        new_width = round(height * target_ratio)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = round(width / target_ratio)
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))


def remove_background(image, session):
    buffer = io.BytesIO()
    image.convert("RGBA").save(buffer, format="PNG")
    result = remove(buffer.getvalue(), session=session)
    return Image.open(io.BytesIO(result)).convert("RGBA")


def composite_background(foreground, color):
    background = Image.new("RGBA", foreground.size, color + (255,))
    background.alpha_composite(foreground)
    return background.convert("RGB")


def prepare_photo(image, width_mm, height_mm, dpi):
    target_w = mm_to_px(width_mm, dpi)
    target_h = mm_to_px(height_mm, dpi)
    cropped = fit_crop(image.convert("RGB"), target_w / target_h)
    return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)


def create_a4_sheet(photo, copies, dpi, margin_mm=8, gap_mm=4):
    page_w = round(A4_W_IN * dpi)
    page_h = round(A4_H_IN * dpi)
    margin = mm_to_px(margin_mm, dpi)
    gap = mm_to_px(gap_mm, dpi)

    sheet = Image.new("RGB", (page_w, page_h), "white")
    photo_w, photo_h = photo.size
    draw = ImageDraw.Draw(sheet)

    # Place copies left-to-right, then wrap to the next row.
    x = margin
    y = margin
    row_height = photo_h

    for index in range(copies):
        if x + photo_w > page_w - margin:
            x = margin
            y += row_height + gap
        if y + photo_h > page_h - margin:
            raise ValueError("The selected photos do not fit on an A4 page.")

        sheet.paste(photo, (x, y))
        # Thin cut guide around each photo.
        draw.rectangle((x, y, x + photo_w, y + photo_h), outline=(180, 180, 180), width=1)
        x += photo_w + gap

    return sheet


class PassportPhotoApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)

        self.original_image = None
        self.processed_image = None
        self.preview_tk = None
        self.session = None
        self.background_color = (255, 255, 255)
        self.last_sheet = None

        self.width_var = tk.StringVar(value=str(DEFAULT_W_MM))
        self.height_var = tk.StringVar(value=str(DEFAULT_H_MM))
        self.dpi_var = tk.StringVar(value=str(DEFAULT_DPI))
        self.copies_var = tk.StringVar(value="5")
        self.bg_var = tk.StringVar(value="White")
        self.status_var = tk.StringVar(value="Upload a photo to begin.")

        self.build_ui()

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=APP_TITLE, font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(top, text="AI background removal · A4 print", foreground="#555").pack(side="left", padx=18)

        controls = ttk.LabelFrame(self.root, text="Controls", padding=10)
        controls.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(controls, text="Upload Photo", command=self.upload_photo).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(controls, text="Remove Background", command=self.ai_remove_background).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(controls, text="Background:").grid(row=0, column=2, padx=(18, 4))
        bg_combo = ttk.Combobox(controls, textvariable=self.bg_var, values=["White", "Blue", "Custom"], state="readonly", width=10)
        bg_combo.grid(row=0, column=3, padx=4)
        bg_combo.bind("<<ComboboxSelected>>", self.background_changed)

        ttk.Button(controls, text="Apply Background", command=self.apply_background).grid(row=0, column=4, padx=5)
        ttk.Button(controls, text="Prepare Photo", command=self.prepare_current_photo).grid(row=0, column=5, padx=5)
        ttk.Button(controls, text="Create 5-Photo A4", command=self.create_print_sheet).grid(row=0, column=6, padx=5)
        ttk.Button(controls, text="Export Sheet", command=self.export_sheet).grid(row=0, column=7, padx=5)
        ttk.Button(controls, text="Print Sheet", command=self.print_sheet).grid(row=0, column=8, padx=5)

        settings = ttk.LabelFrame(self.root, text="Photo Settings", padding=10)
        settings.pack(fill="x", padx=10, pady=(0, 10))

        fields = [
            ("Width (mm)", self.width_var),
            ("Height (mm)", self.height_var),
            ("DPI", self.dpi_var),
            ("Copies", self.copies_var),
        ]
        for col, (label, variable) in enumerate(fields):
            ttk.Label(settings, text=label).grid(row=0, column=col * 2, padx=(5, 4))
            ttk.Entry(settings, textvariable=variable, width=8).grid(row=0, column=col * 2 + 1, padx=(0, 15))

        content = ttk.Frame(self.root, padding=10)
        content.pack(fill="both", expand=True)

        left = ttk.LabelFrame(content, text="Photo Preview", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.preview_label = ttk.Label(left, text="No photo loaded", anchor="center")
        self.preview_label.pack(fill="both", expand=True)

        right = ttk.LabelFrame(content, text="A4 Sheet Preview", padding=10)
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))
        self.sheet_label = ttk.Label(right, text="No print sheet created", anchor="center")
        self.sheet_label.pack(fill="both", expand=True)

        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=5).pack(fill="x", side="bottom")

    def set_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()

    def upload_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        if not path:
            return
        try:
            self.original_image = Image.open(path).convert("RGB")
            self.processed_image = self.original_image.copy()
            self.last_sheet = None
            self.show_preview(self.processed_image, self.preview_label, max_size=(460, 460))
            self.set_status(f"Loaded: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Upload error", str(exc))

    def ai_remove_background(self):
        if self.original_image is None:
            messagebox.showwarning("No photo", "Upload a photo first.")
            return
        try:
            self.set_status("Removing background with AI. First run may download a model...")
            if self.session is None:
                self.session = new_session("u2net")
            self.processed_image = remove_background(self.original_image, self.session)
            self.show_preview(self.processed_image, self.preview_label, max_size=(460, 460), checkerboard=True)
            self.set_status("Background removed. Select a background and apply it.")
        except Exception as exc:
            messagebox.showerror("AI removal error", str(exc))
            self.set_status("Background removal failed.")

    def background_changed(self, _event=None):
        if self.bg_var.get() == "Custom":
            chosen = colorchooser.askcolor(title="Choose background color")
            if chosen[0]:
                self.background_color = tuple(round(value) for value in chosen[0])
            else:
                self.bg_var.set("White")

    def apply_background(self):
        if self.processed_image is None:
            messagebox.showwarning("No photo", "Upload a photo first.")
            return

        if self.bg_var.get() == "White":
            color = (255, 255, 255)
        elif self.bg_var.get() == "Blue":
            color = (0, 102, 204)
        else:
            color = self.background_color

        if self.processed_image.mode != "RGBA":
            messagebox.showinfo("AI required", "Run Remove Background first to create a transparent foreground.")
            return

        self.processed_image = composite_background(self.processed_image, color)
        self.show_preview(self.processed_image, self.preview_label, max_size=(460, 460))
        self.set_status("Background applied.")

    def read_settings(self):
        width = float(self.width_var.get())
        height = float(self.height_var.get())
        dpi = int(self.dpi_var.get())
        copies = int(self.copies_var.get())
        if width <= 0 or height <= 0 or dpi <= 0 or copies <= 0:
            raise ValueError("Width, height, DPI, and copies must be positive.")
        return width, height, dpi, copies

    def prepare_current_photo(self):
        if self.processed_image is None:
            messagebox.showwarning("No photo", "Upload a photo first.")
            return
        try:
            width, height, dpi, _ = self.read_settings()
            self.processed_image = prepare_photo(self.processed_image, width, height, dpi)
            self.show_preview(self.processed_image, self.preview_label, max_size=(460, 460))
            self.set_status(f"Prepared photo: {width} × {height} mm at {dpi} DPI.")
        except Exception as exc:
            messagebox.showerror("Preparation error", str(exc))

    def create_print_sheet(self):
        if self.processed_image is None:
            messagebox.showwarning("No photo", "Upload and prepare a photo first.")
            return
        try:
            width, height, dpi, copies = self.read_settings()
            photo = prepare_photo(self.processed_image, width, height, dpi)
            self.last_sheet = create_a4_sheet(photo, copies, dpi)
            self.show_preview(self.last_sheet, self.sheet_label, max_size=(500, 500))
            self.set_status(f"Created A4 sheet with {copies} copies.")
        except Exception as exc:
            messagebox.showerror("Print layout error", str(exc))

    def export_sheet(self):
        if self.last_sheet is None:
            messagebox.showwarning("No sheet", "Create a print sheet first.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("JPEG", "*.jpg")]
        )
        if not path:
            return

        try:
            width, height, dpi, _ = self.read_settings()
            if path.lower().endswith(".pdf"):
                self.last_sheet.save(path, "PDF", resolution=dpi)
            else:
                self.last_sheet.save(path, "JPEG", quality=95, dpi=(dpi, dpi))
            self.set_status(f"Exported: {os.path.basename(path)}")
            messagebox.showinfo("Export complete", f"Saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))

    def show_preview(self, image, label, max_size=(460, 460), checkerboard=False):
        preview = image.copy()
        if checkerboard and preview.mode == "RGBA":
            bg = Image.new("RGB", preview.size, "white")
            bg.paste(preview, mask=preview.getchannel("A"))
            preview = bg
        else:
            preview = preview.convert("RGB")
        preview.thumbnail(max_size, Image.Resampling.LANCZOS)
        self.preview_tk = ImageTk.PhotoImage(preview)
        label.configure(image=self.preview_tk, text="")
        label.image = self.preview_tk

    def print_sheet(self):
        """Open the Windows print interface for the generated A4 PDF."""

        if self.last_sheet is None:
            messagebox.showwarning(
                "No Sheet",
                "Please create the A4 print sheet first."
            )
            return

        pdf_path = None

        try:
            import tempfile

            _, _, dpi, _ = self.read_settings()

            # Create a temporary PDF file.
            fd, pdf_path = tempfile.mkstemp(
                prefix="passport_print_",
                suffix=".pdf"
            )
            os.close(fd)

            # Save the generated A4 sheet as PDF.
            self.last_sheet.save(
                pdf_path,
                "PDF",
                resolution=dpi
            )

            # Open the Windows print interface.
            # This uses the PDF application's Windows print verb.
            os.startfile(pdf_path, "print")

            self.set_status(
                "Print window opened. Select a printer and check A4 / 100% scale."
            )

        except OSError as exc:
            messagebox.showerror(
                "Windows Print Error",
                "Could not open the Windows print interface.\n\n"
                f"{exc}\n\n"
                "You can open the PDF manually and press Ctrl+P."
            )
            self.set_status("Could not open print window.")

        except Exception as exc:
            messagebox.showerror(
                "Print Error",
                str(exc)
            )
            self.set_status("Printing failed.")

def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    PassportPhotoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
