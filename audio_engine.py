"""Procedural audio and audio-clock helpers."""
from __future__ import annotations

import math
import time
import wave
from pathlib import Path

import numpy as np
import pygame


class AudioEngine:
    def __init__(self) -> None:
        self.sample_rate = 44100
        self.started_at = 0.0
        self.paused_at = 0.0
        self.paused = False
        self.offset_ms = 0
        self.speed = 1.0
        self.track_length = 0.0
        self.using_music = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._create_sounds()

    def _sound(self, frequency: float, duration: float, volume: float = .25,
               waveform: str = "sine") -> pygame.mixer.Sound:
        count = int(self.sample_rate * duration)
        t = np.arange(count, dtype=np.float32) / self.sample_rate
        if waveform == "noise":
            signal = np.random.default_rng(11).uniform(-1, 1, count).astype(np.float32)
        elif waveform == "square":
            signal = np.sign(np.sin(2 * np.pi * frequency * t)).astype(np.float32)
        else:
            signal = np.sin(2 * np.pi * frequency * t).astype(np.float32)
        envelope = np.exp(-t * (8 if duration < .2 else 1.2)).astype(np.float32)
        signal *= envelope * volume
        stereo = np.column_stack((signal, signal))
        pcm = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)
        return pygame.sndarray.make_sound(pcm.copy())

    def _create_sounds(self) -> None:
        self.sounds = {
            "normal": self._sound(880, .10, .28),
            "whistle": self._sound(1320, .13, .22),
            "finish": self._sound(440, .22, .30, "square"),
            "clap": self._sound(240, .08, .27, "noise"),
            "combobreak": self._sound(180, .18, .24, "square"),
            "sliderslide": self._sound(760, .08, .10),
            "spinnerspin": self._sound(520, .08, .10),
            "spinnerbonus": self._sound(1760, .24, .26),
        }

    def apply_skin(self, skin) -> None:
        self._create_sounds()
        for name, path in skin.sounds.items():
            try:
                self.sounds[name] = pygame.mixer.Sound(str(path))
            except pygame.error:
                continue

    def generated_track(self, speed: float = 1.0) -> pygame.mixer.Sound:
        duration = 24.0
        count = int(self.sample_rate * duration)
        audio = np.zeros(count, dtype=np.float32)
        beat = .5
        for index, start in enumerate(np.arange(.0, duration, beat)):
            begin = int(start * self.sample_rate)
            length = min(int(.22 * self.sample_rate), count - begin)
            t = np.arange(length, dtype=np.float32) / self.sample_rate
            note = (110, 164.81, 220, 164.81)[(index // 4) % 4]
            tone = np.sin(2 * np.pi * note * t) + .34 * np.sin(4 * np.pi * note * t)
            tone *= np.exp(-t * 13) * .27
            audio[begin:begin + length] += tone
            if index % 4 == 2:
                click_len = int(.035 * self.sample_rate)
                noise = np.random.default_rng(index).uniform(-1, 1, click_len)
                audio[begin:begin + click_len] += noise * np.exp(-np.arange(click_len) / 300) * .12
        audio = np.clip(audio, -.95, .95)
        if speed != 1.0:
            indices = np.linspace(0, len(audio) - 1, int(len(audio) / speed))
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
        pcm = (np.column_stack((audio, audio)) * 32767).astype(np.int16)
        self.track_length = len(audio) / self.sample_rate
        return pygame.sndarray.make_sound(pcm.copy())

    def play(self, audio_path: Path | None, speed: float = 1.0) -> None:
        self.stop()
        self.speed = speed
        self.started_at = time.perf_counter()
        self.paused = False
        self.using_music = False
        if audio_path and audio_path.exists():
            try:
                pygame.mixer.music.load(str(audio_path))
                pygame.mixer.music.play()
                self.using_music = True
                self.track_length = 0
                return
            except pygame.error:
                pass
        self.generated_track(speed).play()

    def position(self) -> float:
        if self.paused:
            return self.paused_at
        elapsed = max(0.0, time.perf_counter() - self.started_at)
        if self.using_music:
            played_ms = pygame.mixer.music.get_pos()
            if played_ms >= 0:
                elapsed = played_ms / 1000
        return elapsed * self.speed + self.offset_ms / 1000

    def pause(self) -> None:
        if not self.paused:
            self.paused_at = self.position()
            self.paused = True
            if self.using_music:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.pause()

    def resume(self) -> None:
        if self.paused:
            self.started_at = time.perf_counter() - self.paused_at / self.speed
            self.paused = False
            if self.using_music:
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.unpause()

    def stop(self) -> None:
        pygame.mixer.music.stop()
        pygame.mixer.stop()
        self.using_music = False
        self.paused = False

    def hit(self, sound_name: str = "normal") -> None:
        self.sounds.get(sound_name, self.sounds.get("normal")).play()

    @staticmethod
    def write_builtin_wav(path: Path) -> None:
        """Create a portable WAV copy of the bundled procedural song."""
        rate = 44100
        duration = 24
        audio = np.zeros(rate * duration, dtype=np.float32)
        for i, start in enumerate(np.arange(0, duration, .5)):
            begin = int(start * rate)
            t = np.arange(min(int(.22 * rate), len(audio) - begin), dtype=np.float32) / rate
            note = (110, 164.81, 220, 164.81)[(i // 4) % 4]
            audio[begin:begin + len(t)] += (np.sin(2 * np.pi * note * t) + .34 * np.sin(4 * np.pi * note * t)) * np.exp(-t * 13) * .27
        stereo = np.clip(audio, -.95, .95)
        pcm = (np.column_stack((stereo, stereo)) * 32767).astype("<i2")
        with wave.open(str(path), "wb") as target:
            target.setnchannels(2)
            target.setsampwidth(2)
            target.setframerate(rate)
            target.writeframes(pcm.tobytes())
