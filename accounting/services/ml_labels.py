"""
ML-based label predictor: learns from user-labelled transactions (description -> label).
Prioritises user-defined labels and past user choices; uses TF-IDF + classifier.
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import numpy as np

from accounting.models import AccountLabel, BankTransaction


def _tokenize(text):
    """Simple tokenizer: lowercased words and numbers."""
    if not text:
        return []
    text = re.sub(r'[^\w\s]', ' ', (text or '').lower())
    return text.split()


class LabelPredictor:
    """
    Train on (description, label_id) from BankTransaction where label_id is not null.
    Predict label for new descriptions; prioritises labels that user has used.
    """
    def __init__(self, min_samples=2):
        self.min_samples = min_samples
        self.pipeline = None
        self.label_ids_ = None
        self.id_to_label = None

    def get_training_data(self):
        """Get (description, label_id) from all user-labelled transactions."""
        qs = (
            BankTransaction.objects
            .filter(label_id__isnull=False)
            .values('description', 'reference', 'label_id')
        )
        texts = []
        labels = []
        for row in qs:
            combined = f"{row['description']} {row['reference'] or ''}".strip()
            if combined:
                texts.append(combined)
                labels.append(row['label_id'])
        return texts, labels

    def fit(self):
        """Fit pipeline on user-labelled data. Uses user-defined labels as class set when possible."""
        texts, label_ids = self.get_training_data()
        if len(texts) < self.min_samples or len(set(label_ids)) < 2:
            self.pipeline = None
            self.label_ids_ = list(
                AccountLabel.objects.filter(is_user_defined=True).values_list('id', flat=True)
            )[:20]
            self.id_to_label = dict(AccountLabel.objects.filter(id__in=self.label_ids_).values_list('id', 'name'))
            return self

        # Prefer user-defined labels; include any label that appears in data
        user_label_ids = set(AccountLabel.objects.filter(is_user_defined=True).values_list('id', flat=True))
        seen_ids = set(label_ids)
        self.label_ids_ = sorted(user_label_ids | seen_ids)
        self.id_to_label = dict(AccountLabel.objects.filter(id__in=self.label_ids_).values_list('id', 'name'))

        vectorizer = TfidfVectorizer(
            tokenizer=_tokenize,
            max_features=5000,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        clf = LogisticRegression(max_iter=500, class_weight='balanced', random_state=42)
        self.pipeline = Pipeline([('tfidf', vectorizer), ('clf', clf)])

        y = np.array([self.label_ids_.index(lid) for lid in label_ids])
        self.pipeline.fit(texts, y)
        return self

    def predict(self, description, reference='', top_k=3):
        """
        Predict labels for one transaction. Returns list of (label_id, confidence).
        If not enough training data, returns empty or fallback from user labels.
        """
        text = f"{description or ''} {reference or ''}".strip()
        if not text and self.id_to_label:
            return [(lid, 0.0) for lid in self.label_ids_[:top_k]]

        if self.pipeline is None:
            if self.id_to_label:
                return [(lid, 0.0) for lid in list(self.id_to_label.keys())[:top_k]]
            return []

        try:
            probs = self.pipeline.predict_proba([text])[0]
            idx = np.argsort(-probs)[:top_k]
            return [
                (self.label_ids_[i], float(probs[i]))
                for i in idx
                if i < len(self.label_ids_)
            ]
        except Exception:
            if self.id_to_label:
                return [(lid, 0.0) for lid in list(self.id_to_label.keys())[top_k]]
            return []


def get_singapore_tax_guidance():
    """
    Static guidance for common gym transaction types aligned with Singapore business tax.
    Used to advise user on suitable labels (revenue vs expense categories).
    """
    return [
        {
            'keywords': ['membership', 'subscription', 'gym fee', 'monthly fee', 'annual fee', 'sign up'],
            'suggested_category': 'revenue',
            'note': 'Member fees are typically taxable revenue (income).',
        },
        {
            'keywords': ['rent', 'lease', 'utilities', 'electric', 'water', 'sp services', 'pub'],
            'suggested_category': 'expense',
            'note': 'Rent and utilities are deductible operating expenses.',
        },
        {
            'keywords': ['salary', 'wages', 'cpf', 'payroll', 'staff'],
            'suggested_category': 'expense',
            'note': 'Employee costs are deductible; ensure CPF records for IRAS.',
        },
        {
            'keywords': ['equipment', 'machine', 'treadmill', 'weights', 'purchase'],
            'suggested_category': 'expense',
            'note': 'Equipment may be capitalised or claimed under capital allowances.',
        },
        {
            'keywords': ['insurance', 'insurer'],
            'suggested_category': 'expense',
            'note': 'Business insurance is tax deductible.',
        },
        {
            'keywords': ['refund', 'reversal', 'reversal of'],
            'suggested_category': 'other',
            'note': 'Refunds reduce revenue or expense; label to match original type.',
        },
    ]
