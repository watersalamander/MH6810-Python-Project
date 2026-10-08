# Speaker notes: 15-minute talk, 6 presenters

Timing is estimated from word count at 140 words per minute. Each segment is about 2.5 minutes. The same script is in the notes pane of every slide in `presentation.pptx`. Replace *Presenter N* with names.

| Segment | Presenter | Slides | Words | Est. time |
|---|---|---|---|---|
| 1 | Presenter 1 | 1, 2, 3 | 343 | 2:27 |
| 2 | Presenter 2 | 4, 5, 6 | 372 | 2:39 |
| 3 | Presenter 3 | 7, 8 | 341 | 2:26 |
| 4 | Presenter 4 | 9, 10 | 302 | 2:09 |
| 5 | Presenter 5 | 11, 12 | 339 | 2:25 |
| 6 | Presenter 6 | 13, 14, 15 | 378 | 2:42 |
| | **Total** | 1–15 | | **14:49** |

## Segment 1: Presenter 1 (slides 1–3, ≈ 2:27)

### Slide 1: Title (≈ 43 s)

Good morning everyone. We are Group [XX], and our project asks a very practical question: after a major earthquake, can a simple, transparent model tell inspectors which buildings to visit first? We worked with records of 260,601 buildings surveyed after the 2015 Gorkha earthquake in Nepal, and we deliberately limited ourselves to logistic regression so that every prediction can be explained. Over the next fifteen minutes, six of us will walk you through the data, our preprocessing, the two ideas we are most proud of, how we trained and tested the models, what we found, and where we would go next.

### Slide 2: Data set description (≈ 47 s)

Our data come from the DrivenData competition Richter's Predictor, based on Nepal's post-earthquake building survey. There are 260,601 labelled buildings, each described by 38 features, plus 86,868 unlabelled buildings that we only use for a competition submission. The features fall into four groups. Location is given as three nested region levels, from 31 broad regions down to 11,595 local areas. Then size and age, construction details such as foundation, roof and eleven superstructure-material flags, and finally use and ownership. The data are clean, with no missing values, but the categorical codes are anonymised letters, so we can say a foundation of type 'i' is safer, not exactly what 'i' is.

### Slide 3: Problem statement (≈ 57 s)

Here is our problem statement. After an earthquake, inspection teams are scarce and there are hundreds of thousands of buildings. If a model can estimate how badly each building was damaged from information that is already on record, its structure and its location, teams can visit the most dangerous buildings first. Technically this is a three-class classification problem, and the classes are ordered, grade 1 to grade 3. We report micro-F1, which is the competition metric and equals accuracy, and macro-F1, which gives the rare low-damage class equal weight. Because the real goal is prioritisation, we also rank buildings by their predicted probability of grade 3 and measure how many destroyed buildings an inspection list catches. Finally, we restricted ourselves to logistic regression, a model that is transparent and easy to audit.

*Hand over to Presenter 2.*

## Segment 2: Presenter 2 (slides 4–6, ≈ 2:39)

### Slide 4: Exploration: materials (≈ 45 s)

We started with exploratory analysis, done on the training split only so the holdout stayed untouched. The biggest structural signal is the building material. About 76% of buildings are built from mud-mortar stone, and 38% of those were essentially destroyed. Compare engineered reinforced concrete: only 2% reached grade 3, and 64% had only low damage. Foundation and roof types show the same pattern, which you can see in our report. Notice also that the classes are imbalanced: grade 2 is 57% of buildings and grade 1 only 10%, so always guessing grade 2 already scores 0.57, and grade 1 will be the hardest class.

### Slide 5: Exploration: location (≈ 42 s)

The second key finding is geography. Each bar is one of the 31 top-level regions, sorted by its share of destroyed buildings. In region 26 only 9% of buildings reached grade 3; in region 17 it was 81%. The same mud-stone house fares very differently depending on how strongly the ground shook, and location is our best proxy for that. This told us two things: location must be in the model, and the finer location levels, with thousands of local areas, probably carry even more signal, if we can encode them without overfitting. That is one of our highlights.

### Slide 6: Cleaning and feature engineering (≈ 72 s)

Every preprocessing step lives inside a single scikit-learn pipeline, so in cross-validation each step is re-fitted on the training folds only. That is how we avoid data leakage. The data had no missing values, but 1,390 buildings have an age of 995 years, which is clearly a placeholder. Instead of treating them as very old buildings, we add a flag and replace the age with the training median; the flag matters because these buildings are actually damaged less often. Age, area and height are right-skewed, so we log-transform and standardise them. Categorical columns and the top region level are one-hot encoded, and the two fine location levels are target-encoded, which we'll explain next. For feature engineering we tested four candidates, each added on its own and compared fold by fold. We kept only features that improved the mean and won in at least four of five folds: floors_x_log_age. Overall, engineered features changed micro-F1 by +0.02 pp, which is small. Most of the signal is already in the raw features.

*Hand over to Presenter 3.*

## Segment 3: Presenter 3 (slides 7–8, ≈ 2:26)

### Slide 7: Highlight: geo target encoding (≈ 76 s)

Our first highlight is how we used location. The finest level has 11,595 villages. One-hot encoding that would create thousands of sparse columns and overfit. Instead, we used target encoding: each village is replaced by three numbers, its observed share of grade 1, 2 and 3 buildings, smoothed toward the overall mix when a village is small. The danger with target encoding is leakage, because a building's own label would leak into its feature. scikit-learn's TargetEncoder cross-fits internally, so a building's encoding is always computed from other buildings, and because it sits in our pipeline it is re-fitted inside every CV fold. The effect is the biggest jump in the whole project. Structure alone gives 0.591; adding the region one-hot gives 0.672; and the target-encoded villages take us to 0.735, a gain of +6.3 pp from this one idea. Intuitively, the model now knows how badly each neighbourhood was hit, which is exactly the information an inspector would ask for first. Villages that never appear in training, 0.4% of the test set, simply receive the overall class mix.

### Slide 8: Highlight: ordinal vs multinomial (≈ 70 s)

Our second highlight tests whether the ordering of the damage grades can be exploited. A standard multinomial model treats grades 1, 2 and 3 as unrelated labels. Our ordinal version instead fits two binary logistic models: one for 'worse than grade 1' and one for 'worse than grade 2', then turns them into three class probabilities. Compared with the multinomial model on identical features, the ordinal approach changed micro-F1 by -0.06 pp and macro-F1 by -0.04 pp, so it made no real difference. This is a negative result, but an informative one: with only three classes the multinomial model is flexible enough to learn the ordering on its own. We also tried class weighting. It lowered macro-F1 by 0.88 pp and raised grade-1 recall from 0.47 to 0.83, but micro-F1 moved by -4.43 pp. Macro-F1 does not improve either, because many grade-2 buildings are now wrongly called grade 1, so grade-1 precision collapses. So weighting is a policy choice, not a free improvement.

*Hand over to Presenter 4.*

## Segment 4: Presenter 4 (slides 9–10, ≈ 2:09)

### Slide 9: Training and testing procedure (≈ 65 s)

Now, how we trained and tested. We first split the labelled data 80 to 20, stratified by damage grade. The 20 percent holdout, 52,121 buildings, was locked away and used exactly once at the very end. Everything else, comparing experiments and tuning, used stratified five-fold cross-validation on the 80 percent. Because every preprocessing step lives in the pipeline, encoders and scalers are re-fitted inside each fold, so no fold ever sees statistics from its validation data. We ran seven experiments, each adding one idea: a majority baseline, structure only, plus region, plus target-encoded villages, plus engineered features, then a class-balanced and an ordinal variant. The best of the last three, E4, was tuned with GridSearchCV over C from 0.01 to 100, and the best C was 0.3. We checked convergence for every single fit. Finally, after the holdout evaluation, the model was refit on all labelled data to produce our competition submission.

### Slide 10: Experimental results (≈ 64 s)

This chart shows cross-validated micro-F1 for every experiment, with error bars across the five folds. The majority baseline scores 0.569. Structure alone lifts this to 0.591, which is useful but modest. Adding the 31 regions gains +8.1 pp, and the target-encoded village levels add another +6.3 pp, the largest single step. Engineered features change micro-F1 by only +0.02 pp. The balanced and ordinal variants score 0.691 and 0.735. The fold-to-fold standard deviations are tiny, at most 0.19 percentage points, so the big steps are not noise. The orange bar marks the configuration we carried forward to tuning. Two lessons stand out. First, what a building is made of matters, but on its own it cannot tell a mud-stone house near the epicentre from one far away; location supplies that context. Second, once location is in, extra hand-made features add almost nothing, so in this problem better information beats cleverer transformations.

*Hand over to Presenter 5.*

## Segment 5: Presenter 5 (slides 11–12, ≈ 2:25)

### Slide 11: Holdout performance (≈ 68 s)

Now the moment of truth: the holdout, used once. The tuned model scores a micro-F1 of 0.740 and a macro-F1 of 0.680. That is almost identical to the cross-validated estimate of 0.735, which tells us we did not overfit our model selection. The confusion matrix shows where the model succeeds and fails. Grade 2 is recalled 85% of the time and grade 3 63%. Grade 1 is the hardest, at 48%, because it is rare and often looks like grade 2. Importantly, mistakes are almost always between neighbouring grades: only 0.5% of destroyed buildings are mistaken for low damage, which is the costly error for inspectors. The largest error is grade-3 buildings predicted as grade 2, 36% of them. Many destroyed buildings look structurally ordinary on paper, and what tipped them over, such as local shaking, is not in the data. Precision tells the other side: when the model says grade 3, it is right 76% of the time.

### Slide 12: Prioritisation analysis (≈ 77 s)

This slide connects the model back to our problem statement. We ranked every holdout building by its predicted probability of grade 3, the near-destroyed class, and asked: if inspectors work down this list, how many destroyed buildings do they find? Inspecting the top 10 percent finds 28% of all grade-3 buildings; the top 20 percent finds 50%; the top 30 percent finds 66%. A random order would find only 10, 20 and 30 percent, so the ranking is 2.8 times better than random at the top of the list. Within the top 10 percent, 93% of buildings really are grade 3. To make this concrete: in our holdout of 52,121 buildings, the first 5,212 visits on the list would reach about 4,865 destroyed buildings, while a random order would reach about 1,744. In practice, that means the first teams sent out spend most of their time at the buildings that need them most. The curve also shows diminishing returns: after about half the list, most remaining buildings are lower risk, which is useful when planning how many teams to deploy.

*Hand over to Presenter 6.*

## Segment 6: Presenter 6 (slides 13–15, ≈ 2:42)

### Slide 13: Interpretation (≈ 72 s)

Because we used logistic regression, we can open the model and read it. This chart shows odds ratios for grade-3 damage; red bars raise the odds and blue bars lower them. The strongest risk factors are superstructure: mud mortar stone, age and superstructure: stone flag. The strongest protective factors are foundation type = i, roof type = x and superstructure: cement mortar brick. For materials, mud-mortar stone multiplies the odds of destruction by about 1.4, while cement-mortar brick multiplies them by 0.63 and engineered reinforced concrete by 0.84. In plain language, heavy, brittle construction such as stone held together with mud fails badly in strong shaking, while engineered reinforced concrete and cement-bonded walls hold together. This matches engineering intuition, which gives us confidence that the model learned real physics rather than quirks of the data. We left two things out of this chart: location features, which are the strongest predictors but describe how hard the ground shook rather than the building, and very rare flags, whose estimates are unreliable.

### Slide 14: Summary of achievements (≈ 45 s)

To summarise. Our final logistic regression reaches a holdout micro-F1 of 0.740, +17.2 pp above the majority baseline. Translated into the problem statement, inspecting just the top 20 percent of buildings on our list finds 50% of the destroyed ones. The single biggest technical contribution was leakage-safe target encoding of the village-level location. We were strict about methodology: every transformation is inside one pipeline, and the holdout was scored once. We ran seven controlled experiments and report the ones that did not help as honestly as the ones that did. And the whole project, from raw CSV to this deck, is reproducible with one command.

### Slide 15: Future directions (≈ 45 s)

Finally, where would we go next? The most valuable addition would be measured ground shaking, for example peak ground acceleration from USGS ShakeMap, instead of letting region ids act as a proxy. Second, interactions such as material by region would let the model learn that mud-stone is especially dangerous where shaking was strongest, while staying linear and interpretable. Third, a proportional-odds model with shared slopes might use the ordering better. Fourth, decision thresholds should come from inspection capacity, with calibrated probabilities. Lastly, a gradient-boosting benchmark would show how much accuracy we trade for transparency. Thank you for listening; we are happy to take questions.
