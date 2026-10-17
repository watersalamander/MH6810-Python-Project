# Speaker notes: 20-minute talk, 6 presenters

Timing is estimated from word count at 140 words per minute. Each segment is about 3.3 minutes; segments are contiguous slides balanced automatically by speaking time. The same script is in the notes pane of every slide in `presentation.pptx`. Replace *Presenter N* with names.

| Segment | Presenter | Slides | Words | Est. time |
|---|---|---|---|---|
| 1 | Presenter 1 | 1, 2, 3, 4 | 499 | 3:33 |
| 2 | Presenter 2 | 5, 6, 7, 8 | 499 | 3:33 |
| 3 | Presenter 3 | 9, 10 | 431 | 3:04 |
| 4 | Presenter 4 | 11, 12, 13 | 471 | 3:21 |
| 5 | Presenter 5 | 14, 15, 16, 17 | 504 | 3:36 |
| 6 | Presenter 6 | 18, 19, 20, 21 | 496 | 3:32 |
| | **Total** | 1–21 | | **20:42** |

## Segment 1: Presenter 1 (slides 1–4, ≈ 3:33)

### Slide 1: Title (≈ 43 s)

Good morning everyone. We are Group [XX], and our project asks a very practical question: after a major earthquake, can a simple, transparent model tell inspectors which buildings to visit first? We worked with records of 260,601 buildings surveyed after the 2015 Gorkha earthquake in Nepal, and we compared three models: a transparent logistic regression, a random forest and gradient boosting. Over the next twenty minutes, six of us will walk you through the data, our preprocessing, the two ideas we are most proud of, how we trained and tested the models, what we found, and where we would go next.

### Slide 2: Data set description (≈ 47 s)

Our data come from the DrivenData competition Richter's Predictor, based on Nepal's post-earthquake building survey. There are 260,601 labelled buildings, each described by 38 features, plus 86,868 unlabelled buildings that we only use for a competition submission. The features fall into four groups. Location is given as three nested region levels, from 31 broad regions down to 11,595 local areas. Then size and age, construction details such as foundation, roof and eleven superstructure-material flags, and finally use and ownership. The data are clean, with no missing values, but the categorical codes are anonymised letters, so we can say a foundation of type 'i' is safer, not exactly what 'i' is.

### Slide 3: Problem statement (≈ 51 s)

Here is our problem statement. After an earthquake, inspection teams are scarce and there are hundreds of thousands of buildings. If a model can estimate how badly each building was damaged from information that is already on record, its structure and its location, teams can visit the most dangerous buildings first. Technically this is a three-class classification problem with ordered classes, grade 1 to grade 3. Because the real goal is prioritisation, we also rank buildings by their predicted probability of grade 3 and measure how many destroyed buildings an inspection list catches. Finally, we compare three models: logistic regression, which is transparent and easy to audit, and two tree ensembles, which are more flexible but harder to explain.

### Slide 4: Exploration: class imbalance (≈ 72 s)

This chart shows how many buildings fall into each damage grade, measured on our training split. Grade 2 dominates with 57% of buildings, grade 3 follows with 33%, and grade 1, low damage, is only 10%, about one building in 10. This matters for three reasons. First, it sets the bar: a model that ignores the data and always answers grade 2 is already right 57% of the time, a micro-F1 of 0.569. Second, it is why we report two metrics. Micro-F1 counts every building equally, so it is dominated by grade 2; it equals plain accuracy. Macro-F1 averages the F1 score of each grade with equal weight, so the rare grade 1 counts as much as grade 2. The always-grade-2 model gets a macro-F1 of only 0.242, which exposes it immediately. Third, it shaped our procedure. Every split and every cross-validation fold is stratified, so each one keeps the same 10, 57, 33 percent mix, and we tested class weighting, which we come back to in the highlights.

*Hand over to Presenter 2.*

## Segment 2: Presenter 2 (slides 5–8, ≈ 3:33)

### Slide 5: Exploration: materials (≈ 45 s)

We started with exploratory analysis, done on the training split only so the holdout stayed untouched. The biggest structural signal is the building material. About 76% of buildings are built from mud-mortar stone, and 38% of those were essentially destroyed. Compare engineered reinforced concrete: only 2% reached grade 3, and 64% had only low damage. Foundation and roof types show the same pattern. Foundation type r, used by 84% of buildings, has a grade-3 rate of 38%, while foundation type i has only 2%, and roof type x only 4%. The codes are anonymised, but these protective types behave exactly like engineered, reinforced construction.

### Slide 6: Exploration: location (≈ 53 s)

The second key finding is geography. Each bar is one of the 31 top-level regions, sorted by its share of destroyed buildings. In region 26 only 9% of buildings reached grade 3; in region 17 it was 81%. Location is our best proxy for how strongly the ground shook. Remember that location comes at three nested levels: 31 regions, 1,414 sub-regions and 11,595 local areas, each sitting inside the level above, a bit like province, district and village. This chart only uses the coarsest level. This told us two things: location must be in the model, and the finer location levels, with thousands of local areas, probably carry even more signal, if we can encode them without overfitting. That is one of our highlights.

### Slide 7: Pre-processing overview (≈ 59 s)

Before the models see any data, every building goes through the six steps across the top of this slide; the next slides take them one at a time. The important design choice is that all six steps live inside a single scikit-learn pipeline. Several steps learn something from the data, for example the median age, the mean and spread used for scaling, or each area's damage rate. If we learned those on all the data before splitting, the validation buildings would have helped build their own features and our scores would look better than they really are. That is called data leakage. Because everything is in one pipeline, cross-validation re-fits every step on the training folds only. On the right: the trees need no scaling and use simple integer codes, but all three models get the same information.

### Slide 8: Cleaning: the age placeholder (≈ 57 s)

The data had no missing values at all, but one column hides a problem. When we listed the distinct values of age, they run from 0 up to 200 years and then jump straight to 995, with nothing in between. A building 995 years old is not plausible here; 995 is a code for 'age unknown'. It appears on 1,390 buildings, about half a percent. We could simply delete those rows, but the placeholder actually carries information: these buildings were destroyed less often, 29% against 33% for the rest. So we do two things. We add a yes-or-no column that remembers the age was unknown, and we replace 995 with the median age of the training data. Because this happens inside the pipeline, the median is recomputed from the training folds every time.

*Hand over to Presenter 3.*

## Segment 3: Presenter 3 (slides 9–10, ≈ 3:04)

### Slide 9: Scaling and encoding (≈ 96 s)

Next, we make every column readable for the models. On the left are the numeric columns. Age, footprint area and height are strongly skewed: most buildings are small and young, but a few are very large or very old. Area, for example, has a skewness of 3.5. Taking log of one plus x squeezes that long tail and brings area down to 0.4, close to symmetric. We then standardise each column to a mean of zero and a spread of one, so that logistic regression treats all features on the same scale. Trees skip this step: they only ask 'is the value above some threshold', which scaling does not change. On the right are the eight letter-coded columns, such as foundation type. A model cannot read letters, so for logistic regression each letter becomes its own yes-or-no column; this is one-hot encoding, and it avoids pretending that one letter is bigger than another. In the table, a building with foundation r gets a one in the is-r column and zeros elsewhere, while the trees simply see the code zero. The trees get a single column of integer codes and learn which codes to group together. The 31 top-level regions are handled the same way. The two fine location levels are too large for this, and they get special treatment, which is our first highlight.

### Slide 10: Feature engineering (≈ 89 s)

We also tried to create new features from existing columns. The table shows the four candidates and the idea behind each: floors times log of age for buildings that are both tall and old, the ratio of footprint to height for squat versus slender shapes, the average storey height, and the number of materials a building uses. To test them fairly, we added each candidate on its own to our best logistic-regression setup and scored it on exactly the same five folds. Because the folds are identical, we can compare fold by fold, and we only kept a feature if it improved the average and won in at least four of the five folds. Only floors_x_log_age passed, winning all five folds, but its gain is just +0.02 pp. The other three moved the average by at most 0.004 points and won at most 2 of five folds, so they were dropped as noise. This is also why the fold rule matters: judged on the average alone, two of the dropped features would have looked like tiny improvements. The honest conclusion is that the raw survey columns already contain almost all the signal. As you will see, adding better information, namely location, matters far more than clever transformations.

*Hand over to Presenter 4.*

## Segment 4: Presenter 4 (slides 11–13, ≈ 3:21)

### Slide 11: Highlight: target encoding explained (≈ 93 s)

Our first highlight is how we handled the fine location levels, so let us explain it with an example. Every building has an area ID, but the ID is just a name: area 4523 is not bigger or more damaged than area 7. One-hot encoding would need 13,009 columns. Target encoding takes a different approach: instead of the area's name, we give the model the area's damage history. Look at the two illustrative areas on the left. In area A, 15 percent of buildings were grade 1, 60 percent grade 2 and 25 percent grade 3. In area B, 70 percent were destroyed. Every building then receives its area's three rates, as in the table on the right. So the ID becomes three meaningful numbers that answer: how badly was this neighbourhood hit? Two safety mechanisms make this reliable. First, smoothing: a tiny area with three buildings, all destroyed, would get a grade-3 rate of 100 percent, which is weak evidence, so small areas are pulled toward the overall mix of 10%, 57%, 33%. Second, cross-fitting: if a building's own grade were used to compute its own feature, the feature would partly contain the answer. So the training data is split into five parts, and each part is encoded using rates learned only from the other four.

### Slide 12: Highlight: geo target encoding (≈ 47 s)

So does it work? On the left are three logistic-regression experiments with cross-validated micro-F1. On the right is the short version of the mechanism we just described: compact, smoothed, leakage-safe and easy to interpret. The effect is the biggest jump in the whole project. Structure alone gives 0.591; adding the region one-hot gives 0.672; and the target-encoded villages take us to 0.735, a gain of +6.3 pp from this one idea. Intuitively, the model now knows how badly each neighbourhood was hit, which is exactly the information an inspector would ask for first. Villages that never appear in training, 0.4% of the test set, simply receive the overall class mix.

### Slide 13: Highlight: ordinal vs multinomial (≈ 62 s)

Our second highlight tests whether the ordering of the damage grades can be exploited. A standard multinomial model treats grades 1, 2 and 3 as unrelated labels. Our ordinal version instead fits two binary logistic models: one for 'worse than grade 1' and one for 'worse than grade 2', then turns them into three class probabilities. Compared with the multinomial model on identical features, the ordinal approach changed micro-F1 by -0.06 pp and macro-F1 by -0.04 pp, so it made no real difference. This is a negative result, but an informative one: with only three classes the multinomial model is flexible enough to learn the ordering on its own. We also tried class weighting. It lowered macro-F1 by 0.88 pp and raised grade-1 recall from 0.47 to 0.83, but micro-F1 moved by -4.43 pp. So weighting is a policy choice, not a free improvement.

*Hand over to Presenter 5.*

## Segment 5: Presenter 5 (slides 14–17, ≈ 3:36)

### Slide 14: Training and testing procedure (≈ 51 s)

Now, how we trained and tested. We split the labelled data 80 to 20, stratified by damage grade, and locked the 52,121-building holdout away until the very end. All comparisons and tuning used stratified five-fold cross-validation on the 80 percent, with every encoder re-fitted inside each fold. Five-fold means we train five times, each time holding out a different fifth, and average the scores, so we never need the holdout to make decisions. For logistic regression we ran seven experiments and tuned C on the best one, E4. Each tuned model was scored once on the holdout, but the final model was chosen by cross-validation alone: HistGradientBoosting. It was then refit on all labelled data for our submission.

### Slide 15: Experimental results (≈ 55 s)

We start with model one. This chart shows cross-validated micro-F1 for every logistic-regression experiment, with error bars across the five folds. The majority baseline scores 0.569. Structure alone lifts this to 0.591, which is useful but modest. Adding the 31 regions gains +8.1 pp, and the target-encoded village levels add another +6.3 pp, the largest single step. Engineered features change micro-F1 by only +0.02 pp. The balanced and ordinal variants score 0.691 and 0.735, which is why we carried E4 forward. The fold-to-fold standard deviations are tiny, at most 0.19 percentage points, so the big steps are not noise. The lesson: building material matters, but only location tells a mud-stone house near the epicentre from one far away, and once location is in, hand-made features add almost nothing.

### Slide 16: Three-model comparison (≈ 71 s)

Now the comparison our course asked for: three models on exactly the same features and folds. A quick word on the two new models. A random forest grows many decision trees, each on a random sample of buildings and features, and lets them vote; averaging makes it stable. Gradient boosting instead grows trees one after another, each new tree correcting the mistakes of the trees before it. Logistic regression reaches 0.735 cross-validated micro-F1 and 0.740 on the holdout. The random forest reaches 0.744 and 0.750, and HistGradientBoosting 0.745 and 0.750. So HistGradientBoosting is our final model, chosen on cross-validation only. Its gain over logistic regression is +0.98 pp in cross-validation and +0.93 pp on the holdout: real and consistent, but small. The two tree models are practically tied: on the holdout the random forest is even +0.05 pp ahead, but we fixed in advance that cross-validation decides, so the holdout stays an honest check. Macro-F1 tells a similar story: 0.673, 0.687 and 0.694 in cross-validation.

### Slide 17: Holdout performance (≈ 40 s)

Here is the final model, HistGradientBoosting, on the holdout. It scores a micro-F1 of 0.750 and a macro-F1 of 0.701, close to its cross-validated 0.745, so our model selection did not overfit. Grade 2 is recalled 85% of the time and grade 3 64%; grade 1 is hardest at 55%, because it is rare and often looks like grade 2. The grey numbers are logistic regression, for comparison. Importantly, mistakes are almost always between neighbouring grades: only 0.6% of destroyed buildings are mistaken for low damage, which is the costly error for inspectors.

*Hand over to Presenter 6.*

## Segment 6: Presenter 6 (slides 18–21, ≈ 3:32)

### Slide 18: Prioritisation analysis (≈ 48 s)

This slide connects the models back to our problem statement. We ranked every holdout building by its predicted probability of grade 3 and asked: if inspectors work down this list, how many destroyed buildings do they find? With the final model, the top 10 percent finds 28% of all grade-3 buildings, the top 20 percent 51%, and the top 30 percent 67%, against 10, 20 and 30 percent for a random order. The three curves almost overlap: at 20 percent, logistic regression finds 49.8%, the forest 50.6% and boosting 50.6%. Concretely, in our holdout the first 5,212 visits would reach about 4,914 destroyed buildings, instead of about 1,744 in random order.

### Slide 19: Interpretation (≈ 59 s)

Why does a model call a building high-risk? On the left is logistic regression, which we can read directly: odds ratios for grade-3 damage, red raising and blue lowering the odds. The strongest risk factors are superstructure: mud mortar stone and age; the strongest protective ones are foundation type = i and roof type = x. Mud-mortar stone multiplies the odds of destruction by about 1.4, engineered reinforced concrete by 0.84. Tree ensembles have no coefficients, so on the right we use permutation importance: how much micro-F1 drops when we shuffle one input column. All three models rely first on location, then on construction details such as foundation, material and age, which matches our exploration and engineering intuition. The difference is that importance says how much a feature matters, while the odds ratios also say in which direction.

### Slide 20: Summary of achievements (≈ 56 s)

To summarise. Our final model, HistGradientBoosting, reaches a holdout micro-F1 of 0.750, against 0.569 for always guessing grade 2. Translated into the problem statement, inspecting the top 20 percent of buildings on its list finds 51% of the destroyed ones. The biggest technical contribution was leakage-safe target encoding of village-level location, which helps every model. We compared three models fairly, and the trees beat logistic regression by +0.98 pp, so transparency costs a little accuracy but not much. Every transformation sits inside one pipeline, and each tuned model saw the holdout exactly once. Finally, the whole project, from the raw CSV files to the figures, the report and this deck, is reproducible with one command, and every number you have seen today is read automatically from a single results file.

### Slide 21: Future directions (≈ 50 s)

Finally, where would we go next? The most valuable addition would be measured ground shaking, for example peak ground acceleration from USGS ShakeMap, instead of letting region ids act as a proxy. Second, interaction terms such as material by region could close the gap between logistic regression and the trees while staying interpretable. Third, SHAP values would give the tree models per-building explanations, so the more accurate model could also tell an inspector why a building is flagged. Fourth, decision thresholds should come from inspection capacity and from the cost of missing a destroyed building, and the probabilities should be calibrated so teams can trust the percentages. Thank you for listening; we are happy to take questions.
