from muse.backends.mido import midi_to_muse


if __name__ == "__main__":
    name = 'two_tigers'
    midi_to_muse(f"{name}.mid")