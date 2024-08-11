"""
    Moves ESD texts and audio file into LJSpeech format
"""

import pandas as pd
import shutil
import argparse

speakers_list = [
    "0011",
    "0012",
    "0013",
    "0014",
    "0015",
    "0016",
    "0017",
    "0018",
    "0019",
    "0020",
]


def move_metadata(esd_dir: str, output_dir: str):
    """
    Moves all textfiles to LJSpeech formatted metadata.csv file
    """
    esd = pd.DataFrame()

    for speaker in speakers_list:
        esd = pd.concat(
            [
                esd,
                pd.read_csv(
                    "{0}/{1}/{1}.txt".format(esd_dir, speaker),
                    header=None,
                    sep="\t",
                ),
            ]
        )
    esd = (
        esd.loc[esd[2] == "Angry"]
        .append(esd.loc[esd[2] == "Happy"])
        .append(esd.loc[esd[2] == "Neutral"])
        .append(esd.loc[esd[2] == "Sad"])
        .append(esd.loc[esd[2] == "Surprise"])
    )
    for _, row in esd.iterrows():
        row[2] = "[{0}]".format(row[2].upper()) + " " + row[1]
    esd.to_csv(
        "{0}/metadata.csv".format(output_dir),
        header=None,
        sep="|",
        index=False,
    )


def move_audio(esd_dir: str, output_dir: str):
    """
    Moves all audio file to LJSpeech formatted ESD folder
    """
    WAVS_DIR = "{0}/wavs".format(output_dir)
    EMOTIONS = ["Angry", "Happy", "Neutral", "Sad", "Surprise"]

    for speaker in speakers_list:
        for emotion in EMOTIONS:
            shutil.copytree(
                "{0}/{1}/{2}".format(esd_dir, speaker, emotion),
                WAVS_DIR,
                dirs_exist_ok=True,
            )


"""
    Argument list: 
        --esd_dir - ESD input dir
        --output_dir - LJSpeech formatted output dir
"""

parser = argparse.ArgumentParser()
parser.add_argument(
    "--esd_dir",
    dest="esd_dir",
    type=str,
    help="Path to the ESD input dir",
    required=True,
)
parser.add_argument(
    "--output_dir",
    dest="output_dir",
    type=str,
    help="Path to the output dir",
    required=True,
)
args = parser.parse_args()

move_metadata(args.esd_dir, args.output_dir)
move_audio(args.esd_dir, args.output_dir)
