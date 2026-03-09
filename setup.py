from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="VocalTrack",
    version="0.1.0",
    author="Santiago Barreda",
    description="Real-time audio analysis for vowel and pitch tracking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/santiagobarreda/VocalTrack",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Multimedia :: Sound/Audio :: Analysis",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pyaudio>=0.2.11",
        "parselmouth>=0.4.0",
        "pygame>=2.1.0",
        "numpy>=1.20.0",
    ],
    entry_points={
        "console_scripts": [
            "live_vowel=liveaudio.livevowel:main",
            "live_pitch=liveaudio.livepitch:main",
        ],
    },
)