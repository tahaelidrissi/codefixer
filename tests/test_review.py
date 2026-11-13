import os

import pytest

from codefixer.agent.review import review_diff

_MODELS = [
    pytest.param(
        "groq:openai/gpt-oss-120b",
        marks=pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="no GROQ_API_KEY"),
    ),
    pytest.param(
        "anthropic:claude-haiku-5-5",
        marks=pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY"),
    ),
]

_MINIMAL_DIFF = """\
diff --git a/shop.py b/shop.py
index 1111111..2222222 100644
--- a/shop.py
+++ b/shop.py
@@ -1,2 +1,2 @@
 def calculate_discount(price, rate):
-    return price * rate / 10
+    return price * rate / 100
"""

_SUSPICIOUS_DIFF = """\
diff --git a/shop.py b/shop.py
index 1111111..2222222 100644
--- a/shop.py
+++ b/shop.py
@@ -1,3 +1,4 @@
 def calculate_discount(price, rate):
+    print("debug", price, rate)
     return price * rate / 10

diff --git a/unrelated.py b/unrelated.py
index 3333333..4444444 100644
--- a/unrelated.py
+++ b/unrelated.py
@@ -1,1 +1,1 @@
-x = 1
+x = 2
"""


@pytest.mark.parametrize("model", _MODELS)
def test_review_approves_a_minimal_correct_diff(model):
    review = review_diff(
        "The test test_calculate_discount is failing; calculate_discount returns the wrong result.",
        _MINIMAL_DIFF,
        model=model,
    )

    assert review.summary
    assert review.concerns == ""


@pytest.mark.parametrize("model", _MODELS)
def test_review_flags_an_unrelated_change_and_leftover_debug_code(model):
    review = review_diff(
        "The test test_calculate_discount is failing; calculate_discount returns the wrong result.",
        _SUSPICIOUS_DIFF,
        model=model,
    )

    assert review.summary
    assert review.concerns
