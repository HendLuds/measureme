import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox, Toplevel
from PIL import Image, ImageTk
import numpy as np
import csv  # Alternative for CSV export if pandas is not preferred
import pyperclip  # For copying to clipboard

class ImageMeasureApp:
    def __init__(self, master):
        self.master = master
        master.title("Image Measurement App")

        # Layout configuration
        self.setup_layout()

        # Image and measurement data
        self.original_image = None
        self.scale_factor = None
        self.is_setting_scale = True
        self.scale_points = []
        self.distance_points = []
        self.measurements = []  # Stores (distance_id, distance_in_mu)

    def setup_layout(self):
        # Main layout frames
        self.main_frame = tk.Frame(self.master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas_frame = tk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.info_frame = tk.Frame(self.main_frame, width=200)
        self.info_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_frame.pack_propagate(False)

        # Controls
        self.load_image_button = tk.Button(self.canvas_frame, text="Load Image", command=self.load_image)
        self.load_image_button.pack(side=tk.BOTTOM, pady=5)

        self.export_csv_button = tk.Button(self.info_frame, text="Export to CSV", command=self.export_to_csv)
        self.export_csv_button.pack(side=tk.BOTTOM, pady=5)

        self.copy_clipboard_button = tk.Button(self.info_frame, text="Copy to Clipboard", command=self.copy_to_clipboard)
        self.copy_clipboard_button.pack(side=tk.BOTTOM)

        # Canvas for image
        self.canvas = tk.Canvas(self.canvas_frame, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Info panel for measurements and statistics
        self.setup_info_panel()

    def setup_info_panel(self):
        # Table for displaying measurements
        self.tree = ttk.Treeview(self.info_frame, columns=('ID', 'Distance'), show="headings")
        self.tree.heading('ID', text='ID')
        self.tree.heading('Distance', text='Distance (μm)')
        self.tree.column('ID', anchor=tk.CENTER, width=50)
        self.tree.column('Distance', anchor=tk.CENTER, width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Statistics labels
        self.avg_label = tk.Label(self.info_frame, text="Average: N/A")
        self.avg_label.pack(side=tk.TOP, fill=tk.X, padx=5)

        self.std_dev_label = tk.Label(self.info_frame, text="Std Dev: N/A")
        self.std_dev_label.pack(side=tk.TOP, fill=tk.X, padx=5)

    def load_image(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.original_image = Image.open(file_path)
            self.update_image()

    def update_image(self):
        self.photo = ImageTk.PhotoImage(self.original_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

        # Assuming the safe zone offset is 25 pixels from each edge
        safe_zone_offset = 25
        image_width, image_height = self.original_image.width, self.original_image.height

        # Calculate the coordinates of the safe zone rectangle
        safe_zone_coords = (
            safe_zone_offset, safe_zone_offset,  # Top-left corner
            image_width - safe_zone_offset,      # Bottom-right corner x
            image_height - safe_zone_offset      # Bottom-right corner y
        )

        # Draw the safe zone rectangle
        self.canvas.create_rectangle(safe_zone_coords, outline='green', width=2, dash=(4, 4))
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    def on_canvas_click(self, event):
        self.show_magnified_area(event.x, event.y)

    def show_magnified_area(self, x, y):
        magnification_factor = 5
        size = 50  # Size of the area around the cursor to magnify

        # Calculate the bounds of the magnified area, ensuring it doesn't go outside the image
        left = max(x - size // 2, 0)
        top = max(y - size // 2, 0)
        right = min(x + size // 2, self.original_image.width)
        bottom = min(y + size // 2, self.original_image.height)

        # Adjust the crop area dynamically to prevent distortion and maintain aspect ratio
        if right - left < size:
            if left == 0:  # Too close to the left edge
                right = size
            else:  # Too close to the right edge
                left = self.original_image.width - size
        if bottom - top < size:
            if top == 0:  # Too close to the top edge
                bottom = size
            else:  # Too close to the bottom edge
                top = self.original_image.height - size

        region = self.original_image.crop((left, top, right, bottom))
        magnified_region = region.resize((size * magnification_factor, size * magnification_factor), Image.NEAREST)

        # Display the magnified view in a new window
        new_window = Toplevel(self.master)
        new_window.title("Magnified View")
        magnified_photo = ImageTk.PhotoImage(magnified_region)
        canvas = tk.Canvas(new_window, width=size * magnification_factor, height=size * magnification_factor)
        canvas.pack()
        canvas.create_image(0, 0, anchor=tk.NW, image=magnified_photo)
        canvas.image = magnified_photo  # Keep a reference to avoid garbage collection

        # Mark the cursor position in the magnified view
        cursor_x, cursor_y = (size * magnification_factor) // 2, (size * magnification_factor) // 2
        canvas.create_oval(cursor_x-5, cursor_y-5, cursor_x+5, cursor_y+5, outline='red')

        def on_click_magnified(event, origin_x=x, origin_y=y, win=new_window):
            adjusted_x = origin_x + (event.x // magnification_factor) - (size // 2)
            adjusted_y = origin_y + (event.y // magnification_factor) - (size // 2)
            win.destroy()  # Close the magnified view after selection
            self.process_click(adjusted_x, adjusted_y)

        canvas.bind("<Button-1>", on_click_magnified)

    def mark_point_in_magnification(self, x, y, widget):
        widget.create_oval(x-5, y-5, x+5, y+5, outline='yellow')

    def process_click(self, x, y):
        # Mark the selected point on the actual image immediately
        self.mark_point_on_image(x, y)

        # Add point to the appropriate list based on the current mode (setting scale or measuring distance)
        if self.is_setting_scale:
            self.scale_points.append((x, y))
            if len(self.scale_points) == 2:
                # If two points have been selected, set the scale
                self.set_scale()
        else:
            self.distance_points.append((x, y))
            # If it's the second point for a distance measurement, draw the line and measure the distance
            if len(self.distance_points) == 2:
                self.measure_distance()
                self.distance_points = []  # Clear the points for the next measurement

    def mark_point_on_image(self, x, y):
        # Create a small oval (or dot) at the clicked point on the canvas
        self.canvas.create_oval(x-2, y-2, x+2, y+2, fill='red', outline='red')


    def set_scale(self):
        pixel_distance = np.linalg.norm(np.array(self.scale_points[0]) - np.array(self.scale_points[1]))
        real_distance = simpledialog.askfloat("Scale Setting", "Enter the real-world distance between the points (in micrometers):", parent=self.master)
        if real_distance is not None:
            self.scale_factor = real_distance / pixel_distance
            self.is_setting_scale = False
            messagebox.showinfo("Scale Set", "Scale factor set. Now you can measure distances.")
            self.scale_points = []  # Reset for next use
        else:
            self.scale_points = []  # Clear points if user cancels

    def measure_distance(self):
        pixel_distance = np.linalg.norm(np.array(self.distance_points[0]) - np.array(self.distance_points[1]))
        real_distance = pixel_distance * self.scale_factor
        self.measurements.append(real_distance)
        distance_id = len(self.measurements)
        self.tree.insert('', tk.END, values=(distance_id, f"{real_distance:.2f}"))
        self.update_stats()
        self.canvas.create_line(self.distance_points[0], self.distance_points[1], fill="red", width=2)
        self.distance_points = []  # Reset for next measurement

    def update_stats(self):
        if self.measurements:
            avg_distance = np.mean(self.measurements)
            std_dev = np.std(self.measurements)
            self.avg_label.config(text=f"Average: {avg_distance:.2f} μm")
            self.std_dev_label.config(text=f"Std Dev: {std_dev:.2f} μm")



    def copy_to_clipboard(self):
        # Check if there are any measurements to copy
        if not self.measurements:
            messagebox.showwarning("Copy to Clipboard", "No measurements to copy.")
            return

        # Create a header for the copied text
        clipboard_text = "Distance ID\tDistance (μm)\n"

        # Format each measurement as a line in the text
        for idx, distance in enumerate(self.measurements, 1):
            clipboard_text += f"{idx}\t{distance:.2f}\n"

        # Copy the formatted text to the clipboard
        pyperclip.copy(clipboard_text)

        # Notify the user
        messagebox.showinfo("Copy to Clipboard", "Measurements copied to clipboard.")

    def export_to_csv(self):
        # Check if there are any measurements to export
        if not self.measurements:
            messagebox.showwarning("Export to CSV", "No measurements to export.")
            return

        # Ask the user for a file path to save the CSV
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not file_path:  # Check if the user canceled the save dialog
            return

        # Write the measurements to the CSV file
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            # Write a header row
            writer.writerow(["Distance ID", "Distance (μm)"])

            # Write each measurement as a row in the CSV
            for idx, distance in enumerate(self.measurements, 1):
                writer.writerow([idx, distance])

        # Notify the user
        messagebox.showinfo("Export to CSV", "Measurements exported to CSV successfully.")



    # export_to_csv, and copy_to_clipboard
    # These need to be implemented as per previous instructions and the new functionalities added

def main():
    root = tk.Tk()
    root.geometry("1000x600")
    app = ImageMeasureApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
