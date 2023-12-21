# Code for adapted a transformer-based language model
# Author: Jordan Boyd-Graber
# Date: 26. Sept 2022

import argparse
from collections import Counter
from random import sample

import numpy as np

import pyarrow as pa

from transformers import AutoTokenizer, TrainingArguments, Trainer
from datasets import load_dataset, load_metric

kUNK = "~UNK~"


def accuracy(eval_pred):
    """
    Compute accuracy for the classification task using the
    load_metric function.  This function is needed for the
    compute_metrics argument of the Trainer.

    You shouldn't need to modify this function.

    Keyword args:
    eval_pred -- Output from a classifier with the logits and labels.
    """

    metric = load_metric("accuracy")
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return metric.compute(predictions=predictions, references=labels)


class DatasetTrainer:
    def __init__(self, checkpoint: str = 'distilbert-base-cased', train_set: list[str] = ['guesstrain']):
        """
        Initialize a class to train a fine-tuned BERT model.

        Args:
          checkpoint - model we build off of
          train_set - a list of the folds we use to train the model
        """
        self._checkpoint = checkpoint
        self._train = None
        self._train_fold_name = train_set
        self._dataset = None
        self._tokenized = None
        self._num_categories = 0


    def load_qb_data(self, desired_label: str = 'category', max_labels: int = 5000, min_frequency: int = 3,
                     limit: int = -1):
        """
        Load the QANTA dataset and convert one of its columns into a label we can use for predictions.

        Args:
          desired_label - The column in the dataset to use as our classification label
          max_labels - How many labels total we can have at most
          min_frequency - How many times a label must appear to be counted
          limit - How many examples we have per fold
        """
        self._dataset = load_dataset("qanta", 'mode=full,char_skip=25')

        # TODO: Modify the dataset so that you can predict with the
        # column you want on a subset of the data.

        self._dataset = self._dataset[self._train_fold_name[0]]
        # print('self._dataset',self._dataset)

        if limit > 0:
            self._dataset = self._dataset.select(range(min(limit, len(self._dataset))))


        if desired_label not in self._dataset.column_names:
            raise ValueError(f"Column '{desired_label}' not found in the dataset.")

        labels = self._dataset[desired_label]

        # Build the label set
        label_counter = Counter(labels)
        labels_to_keep = [label for label, count in label_counter.most_common(max_labels) if count >= min_frequency]

        # Map the column into your newly-defined label set
        label_map = {label: idx for idx, label in enumerate(labels_to_keep)}
        # print('label_map', label_map)
        def map_func(ex):
          if desired_label in ex:
              example['label'] = label_map.get(ex[desired_label])
          return ex


        self._num_categories = len(labels_to_keep)
        # And turn that into a class encoding
        self._dataset = self._dataset.map(map_func)
        # print('self._dataset',self._dataset)

    def tokenize_data(self):
        """
        Tokenize our data so that it's ready for BERT.

        You should not need to modify this function.
        """
        tokenizer = AutoTokenizer.from_pretrained("distilbert-base-cased")
        tokenize_function = lambda x: tokenizer(x["full_question"], padding="max_length", truncation=True)
        self._tokenized = self._dataset.map(tokenize_function, batched=True)
        # print(f"Tokenized: {self._tokenized}")
        return self._tokenized

    def load_and_train_model(self, epochs: int = 1):
        """
        Load a BERT sequence classifier and then fine-tune it on our date.

        Args:
          epochs - How many epochs to train.
        """
        # TODO: We have provided code to load the model, but you need to actually train the model, which is not implemented!
        from transformers import AutoModelForSequenceClassification, EvalPrediction


        # TODO: Get rid of this magic number for the number of categories
        # num_categories = 11

        print("Using %i categories" % self._num_categories)
        ds = self._tokenized.train_test_split(test_size=0.1)
        ds_train, ds_test = ds['train'], ds['test']

        model = AutoModelForSequenceClassification.from_pretrained(self._checkpoint, num_labels=self._num_categories)
        training_args = TrainingArguments("trainer", evaluation_strategy="epoch", num_train_epochs=3, logging_dir="./logs")

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=ds_train,
            eval_dataset=ds_test,
            compute_metrics=accuracy,

        )

        trainer.train()
        print(trainer.evaluate())
        return model


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-f')

    argparser.add_argument("--limit", help="Limit folds to this many examples",
                           type=int, default=500, required=False)
    argparser.add_argument("--to_classify", help="Target field that model will try to predict",
                           type=str, default="category")
    argparser.add_argument("--min_frequency", help="How many times must a label appear to be predicted",
                           type=int, default=5)
    argparser.add_argument("--max_label", help="How many labels (maximum) will we predict",
                           type=int, default=5000)
    argparser.add_argument("--ec", help="Extra credit option (df, lazy, or rate)",
                           type=str, default="")

    flags = argparser.parse_args()

    dt = DatasetTrainer()
    dt.load_qb_data(desired_label=flags.to_classify,
                    max_labels=flags.max_label,
                    min_frequency=flags.min_frequency,
                    limit=flags.limit)
    dt.tokenize_data()
    model = dt.load_and_train_model()
    model.save_pretrained("finetuned.model")
