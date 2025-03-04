import os
import argparse
from trainer import Trainer, TrainerArgs
import torch
from torch import nn

from TTS.config.shared_configs import BaseDatasetConfig
from TTS.tts.datasets import load_tts_samples
from TTS.tts.layers.xtts.trainer.gpt_trainer import (
    GPTArgs,
    GPTTrainer,
    GPTTrainerConfig,
    XttsAudioConfig,
)
from TTS.utils.manage import ModelManager

"""
    Argument list: 
        --train_dir - Training dataset directory
        --eval_dir - Evaluation dataset directory
"""

parser = argparse.ArgumentParser()
parser.add_argument(
    "--train_dir",
    dest="train_dir",
    type=str,
    help="Path to the training dataset dir",
    required=True,
)
parser.add_argument(
    "--eval_dir",
    dest="eval_dir",
    type=str,
    help="Path to the evaluation dataset dir",
    required=True,
)
args = parser.parse_args()


# Logging parameters
RUN_NAME = "GPT_XTTS_v2.0_LJSpeech_FT"
PROJECT_NAME = "XTTS_trainer"
DASHBOARD_LOGGER = "tensorboard"
LOGGER_URI = None

# Set here the path that the checkpoints will be saved. Default: ./run/training/
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run", "training")

# Training Parameters
OPTIMIZER_WD_ONLY_ON_WEIGHTS = True  # for multi-gpu training please make it False
START_WITH_EVAL = True  # if True it will star with evaluation
BATCH_SIZE = 3  # set here the batch size
GRAD_ACUMM_STEPS = 84  # set here the grad accumulation steps
# Note: we recommend that BATCH_SIZE * GRAD_ACUMM_STEPS need to be at least 252 for more efficient training. You can increase/decrease BATCH_SIZE but then set GRAD_ACUMM_STEPS accordingly.

# Define here the dataset that you want to use for the fine-tuning on.
config_dataset = BaseDatasetConfig(
    formatter="ljspeech",
    dataset_name="ljspeech",
    path="{0}".format(args.train_dir),
    meta_file_train="{0}/metadata.csv".format(args.train_dir),
    language="en",
)

config_dataset_eval = BaseDatasetConfig(
    formatter="ljspeech",
    dataset_name="ljspeech",
    path="{0}".format(args.eval_dir),
    meta_file_train="{0}/metadata.csv".format(args.eval_dir),
    language="en",
)

# Add here the configs of the datasets
DATASETS_CONFIG_LIST = [config_dataset]
DATASETS_CONFIG_LIST_EVAL = [config_dataset_eval]

# Define the path where XTTS v2.0.1 files will be downloaded
CHECKPOINTS_OUT_PATH = os.path.join(OUT_PATH, "XTTS_v2.0_original_model_files/")
os.makedirs(CHECKPOINTS_OUT_PATH, exist_ok=True)


# DVAE files
DVAE_CHECKPOINT_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/dvae.pth"
MEL_NORM_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/mel_stats.pth"

# Set the path to the downloaded files
DVAE_CHECKPOINT = os.path.join(
    CHECKPOINTS_OUT_PATH, os.path.basename(DVAE_CHECKPOINT_LINK)
)
MEL_NORM_FILE = os.path.join(CHECKPOINTS_OUT_PATH, os.path.basename(MEL_NORM_LINK))

# download DVAE files if needed
if not os.path.isfile(DVAE_CHECKPOINT) or not os.path.isfile(MEL_NORM_FILE):
    print(" > Downloading DVAE files!")
    ModelManager._download_model_files(
        [MEL_NORM_LINK, DVAE_CHECKPOINT_LINK], CHECKPOINTS_OUT_PATH, progress_bar=True
    )


# Download XTTS v2.0 checkpoint if needed
TOKENIZER_FILE_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/vocab.json"
XTTS_CHECKPOINT_LINK = "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/model.pth"

# XTTS transfer learning parameters: You we need to provide the paths of XTTS model checkpoint that you want to do the fine tuning.
TOKENIZER_FILE = os.path.join(
    CHECKPOINTS_OUT_PATH, os.path.basename(TOKENIZER_FILE_LINK)
)  # vocab.json file
XTTS_CHECKPOINT = os.path.join(
    CHECKPOINTS_OUT_PATH, os.path.basename(XTTS_CHECKPOINT_LINK)
)  # model.pth file

# download XTTS v2.0 files if needed
if not os.path.isfile(TOKENIZER_FILE) or not os.path.isfile(XTTS_CHECKPOINT):
    print(" > Downloading XTTS v2.0 files!")
    ModelManager._download_model_files(
        [TOKENIZER_FILE_LINK, XTTS_CHECKPOINT_LINK],
        CHECKPOINTS_OUT_PATH,
        progress_bar=True,
    )


# Training sentences generations
SPEAKER_REFERENCE = [
    os.path.dirname(os.path.abspath(__file__))
    + "/speakers/LJ001-0003.wav"  # speaker reference to be used in training test sentences
]
ANGER_SPEAKER_REFERENCE = [
    os.path.dirname(os.path.abspath(__file__))
    + "/speakers/ANG_Ses05M_script02_2_M024.wav"  # speaker reference to be used in training test sentences
]
HAPPY_SPEAKER_REFERENCE = [
    os.path.dirname(os.path.abspath(__file__))
    + "/speakers/HAP_Ses05M_impro03_M007.wav"  # speaker reference to be used in training test sentences
]
NEUTRAL_SPEAKER_REFERENCE = [
    os.path.dirname(os.path.abspath(__file__))
    + "/speakers/NEU_Ses05M_script03_2_M024.wav"  # speaker reference to be used in training test sentences
]
SAD_SPEAKER_REFERENCE = [
    os.path.dirname(os.path.abspath(__file__))
    + "/speakers/SAD_Ses05F_script01_3_M031.wav"  # speaker reference to be used in training test sentences
]
LANGUAGE = config_dataset.language


def change_embedding_output_dim(model: GPTTrainer):
    new_vocabulary_size = 6683
    new_embedding = nn.Embedding(new_vocabulary_size, 1024)

    old_embedding_weights = model.xtts.gpt.text_embedding.weight.data
    new_embedding.weight.data[
        : old_embedding_weights.size(0), : old_embedding_weights.size(1)
    ] = old_embedding_weights

    model.xtts.gpt.text_embedding = new_embedding


def main():
    # init args and config
    model_args = GPTArgs(
        max_conditioning_length=132300,  # 6 secs
        min_conditioning_length=66150,  # 3 secs
        debug_loading_failures=False,
        max_wav_length=255995,  # ~11.6 seconds
        max_text_length=200,
        mel_norm_file=MEL_NORM_FILE,
        dvae_checkpoint=DVAE_CHECKPOINT,
        xtts_checkpoint=XTTS_CHECKPOINT,  # checkpoint path of the model that you want to fine-tune
        tokenizer_file=TOKENIZER_FILE,
        gpt_num_audio_tokens=1026,
        gpt_start_audio_token=1024,
        gpt_stop_audio_token=1025,
        gpt_use_masking_gt_prompt_approach=True,
        gpt_use_perceiver_resampler=True,
    )
    # define audio config
    audio_config = XttsAudioConfig(
        sample_rate=22050, dvae_sample_rate=22050, output_sample_rate=24000
    )
    # training parameters config
    config = GPTTrainerConfig(
        output_path=OUT_PATH,
        model_args=model_args,
        run_name=RUN_NAME,
        project_name=PROJECT_NAME,
        run_description="""
            GPT XTTS training
            """,
        dashboard_logger=DASHBOARD_LOGGER,
        logger_uri=LOGGER_URI,
        audio=audio_config,
        batch_size=BATCH_SIZE,
        batch_group_size=48,
        eval_batch_size=BATCH_SIZE,
        num_loader_workers=8,
        eval_split_max_size=256,
        print_step=50,
        plot_step=100,
        log_model_step=1000,
        save_step=10000,
        save_n_checkpoints=1,
        save_checkpoints=True,
        # target_loss="loss",
        print_eval=False,
        # Optimizer values like tortoise, pytorch implementation with modifications to not apply WD to non-weight parameters.
        optimizer="AdamW",
        optimizer_wd_only_on_weights=OPTIMIZER_WD_ONLY_ON_WEIGHTS,
        optimizer_params={"betas": [0.9, 0.96], "eps": 1e-8, "weight_decay": 1e-2},
        lr=5e-06,  # learning rate
        lr_scheduler="MultiStepLR",
        # it was adjusted accordly for the new step scheme
        lr_scheduler_params={
            "milestones": [50000 * 18, 150000 * 18, 300000 * 18],
            "gamma": 0.5,
            "last_epoch": -1,
        },
        test_sentences=[
            {
                "text": "[angry] Well, welcome to the human race.  Do you think this is what I had planned?  Do you think that when I proposed that I had this great fantasy going that four years down the road we would end up arguing on the beach over some fish?",
                "speaker_wav": ANGER_SPEAKER_REFERENCE,
                "language": LANGUAGE,
            },
            {
                "text": "[happy] You know- we did some- you know some rock climbing up the waterfalls and went up to this little pool that was up there.  And then, I- it's great. Um- You have to climb this little rock-",
                "speaker_wav": HAPPY_SPEAKER_REFERENCE,
                "language": LANGUAGE,
            },
            {
                "text": "So, did you see much of Peter Burden after the divorce?",
                "speaker_wav": NEUTRAL_SPEAKER_REFERENCE,
                "language": LANGUAGE,
            },
            {
                "text": "[sad] And I got an ideal, watching them all go down.  Everything was being destroyed see and-",
                "speaker_wav": SAD_SPEAKER_REFERENCE,
                "language": LANGUAGE,
            },
        ],
    )

    model = GPTTrainer.init_from_config(config)  # 5753, 6152, 6540, 6541, 6542
    # change_embedding_output_dim(model)

    # load training samples
    train_samples, _ = load_tts_samples(DATASETS_CONFIG_LIST, eval_split=False)
    eval_samples, _ = load_tts_samples(DATASETS_CONFIG_LIST_EVAL, eval_split=False)

    # init the trainer and 🚀
    trainer = Trainer(
        TrainerArgs(
            restore_path=None,  # xtts checkpoint is restored via xtts_checkpoint key so no need of restore it using Trainer restore_path parameter
            skip_train_epoch=False,
            start_with_eval=START_WITH_EVAL,
            grad_accum_steps=GRAD_ACUMM_STEPS,
        ),
        config,
        output_path=OUT_PATH,
        model=model,
        train_samples=train_samples,
        eval_samples=eval_samples,
    )
    trainer.fit()


if __name__ == "__main__":
    main()
