from sonqelra.backends.mido import midi_to_sonqelra


if __name__ == "__main__":
    name = 'two_tigers'
    midi_to_sonqelra(f"{name}.mid")