import tkinter as tk

def librarian_mode():
    print("Librarian Mode activated")

def normal_mode():
    print("Normal Mode activated")

def shut_down():
    print("Shutting down")

# Create the main window
root = tk.Tk()
root.title("Pixi Control Panel")

# Define window size
window_width = 400
window_height = 200
root.geometry(f"{window_width}x{window_height}")

# Define button size
button_width = 20
button_height = 10

# Create a frame to hold the buttons
button_frame = tk.Frame(root)
button_frame.pack(expand=True)

# Create buttons with specified size
librarian_button = tk.Button(button_frame, text="Librarian Mode", command=librarian_mode, width=button_width, height=button_height)
normal_button = tk.Button(button_frame, text="Normal Mode", command=normal_mode, width=button_width, height=button_height)
shutdown_button = tk.Button(button_frame, text="Shutdown", command=shut_down, width=button_width, height=button_height)

# Place buttons on the frame
librarian_button.pack(side="left", padx=10)
normal_button.pack(side="left", padx=10)
shutdown_button.pack(side="left", padx=10)

# Center the frame in both directions
button_frame.pack(expand=True, anchor="center")

# Run the Tkinter event loop
root.mainloop()
