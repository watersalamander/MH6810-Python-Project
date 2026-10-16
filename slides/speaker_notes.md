# Speaker notes: 15-minute talk, 6 presenters

Timing is estimated from word count at 140 words per minute. Each segment is about 2.5 minutes. The same script is in the notes pane of every slide in `presentation.pptx`. Replace *Presenter N* with names.

| Segment | Presenter | Slides | Words | Est. time |
|---|---|---|---|---|
| 1 | Presenter 1 | 1, 2, 3 | 353 | 2:31 |
| 2 | Presenter 2 | 4, 5, 6 | 380 | 2:42 |
| 3 | Presenter 3 | 7, 8 | 341 | 2:26 |
| 4 | Presenter 4 | 9, 10, 11 | 362 | 2:35 |
| 5 | Presenter 5 | 12, 13, 14 | 342 | 2:26 |
| 6 | Presenter 6 | 15, 16 | 325 | 2:19 |
| | **Total** | 1–16 | | **15:01** |

## Segment 1: Presenter 1 (slides 1–3, ≈ 2:31)

### Slide 1: Title (≈ 43 s)

Good morning everyone. We are Group [XX], and our project asks a very practical question: after a major earthquake, can a simple, transparent model tell inspectors which buildings to visit first? We worked with records of 260,601 buildings surveyed after the 2015 Gorkha earthquake in Nepal, and we compared three models: a transparent logistic regression, a random forest and gradient boosting. Over the next fifteen minutes, six of us will walk you through the data, our preprocessing, the two ideas we are most proud of, how we trained and tested the models, what we found, and where we would go next.

### Slide 2: Data set description (≈ 47 s)

Our data come from the DrivenData competition Richter's Predictor, based on Nepal's post-earthquake building survey. There are 260,601 labelled buildings, each described by 38 features, plus 86,868 unlabelled buildings that we only use for a competition submission. The features fall into four groups. Location is given as three nested region levels, from 31 broad regions down to 11,595 local areas. Then size and age, construction details such as foundation, roof and eleven superstructure-material flags, and finally use and ownership. The data are clean, with no missing values, but the categorical codes are anonymised letters, so we can say a foundation of type 'i' is safer, not exactly what 'i' is.

### Slide 3: Problem statement (≈ 61 s)

Here is our problem statement. After an earthquake, inspection teams are scarce and there are hundreds of thousands of buildings. If a model can estimate how badly each building was damaged from information that is already on record, its structure and its location, teams can visit the most dangerous buildings first. Technically this is a three-class classification problem, and the classes are ordered, grade 1 to grade 3. We report micro-F1, which is the competition metric and equals accuracy, and macro-F1, which gives the rare low-damage class equal weight. Because the real goal is prioritisation, we also rank buildings by their predicted probability of grade 3 and measure how many destroyed buildings an inspection list catches. Finally, we compare three models: logistic regression, which is transparent and easy to audit, and two tree ensembles, which are more flexible but harder to explain.

*Hand over to Presenter 2.*

## Segment 2: Presenter 2 (slides 4–6, ≈ 2:42)

### Slide 4: Exploration: materials (≈ 45 s)

We started with exploratory analysis, done on the training split only so the holdout stayed untouched. The biggest structural signal is the building material. About 76% of buildings are built from mud-mortar stone, and 38% of those were essentially destroyed. Compare engineered reinforced concrete: only 2% reached grade 3, and 64% had only low damage. Foundation and roof types show the same pattern, which you can see in our report. Notice also that the classes are imbalanced: grade 2 is 57% of buildings and grade 1 only 10%, so always guessing grade 2 already scores 0.57, and grade 1 will be the hardest class.

### Slide 5: Exploration: location (≈ 42 s)

The second key finding is geography. Each bar is one of the 31 top-level regions, sorted by its share of destroyed buildings. In region 26 only 9% of buildings reached grade 3; in region 17 it was 81%. The same mud-stone house fares very differently depending on how strongly the ground shook, and location is our best proxy for that. This told us two things: location must be in the model, and the finer location levels, with thousands of local areas, probably carry even more signal, if we can encode them without overfitting. That is one of our highlights.

### Slide 6: Cleaning and feature engineering (≈ 76 s)

Every preprocessing step lives inside a single scikit-learn pipeline, so in cross-validation each step is re-fitted on the training folds only. That is how we avoid data leakage. The data had no missing values, but 1,390 buildings have an age of 995 years, which is clearly a placeholder. Instead of treating them as very old buildings, we add a flag and replace the age with the training median; the flag matters because these buildings are actually damaged less often. For logistic regression, age, area and height are log-transformed and standardised, and categoricals are one-hot encoded; the tree models skip the scaling and use integer codes instead. The two fine location levels are target-encoded for all three models, which we'll explain next. For feature engineering we tested four candidates, each added on its own and compared fold by fold. We kept only features that improved the mean and won in at least four of five folds: floors_x_log_age. Overall, engineered features changed micro-F1 by +0.02 pp, which is small. Most of the signal is already in the raw features.

*Hand over to Presenter 3.*

## Segment 3: Presenter 3 (slides 7–8, ≈ 2:26)

### Slide 7: Highlight: geo target encoding (≈ 76 s)

Our first highlight is how we used location. The finest level has 11,595 villages. One-hot encoding that would create thousands of sparse columns and overfit. Instead, we used target encoding: each village is replaced by three numbers, its observed share of grade 1, 2 and 3 buildings, smoothed toward the overall mix when a village is small. The danger with target encoding is leakage, because a building's own label would leak into its feature. scikit-learn's TargetEncoder cross-fits internally, so a building's encoding is always computed from other buildings, and because it sits in our pipeline it is re-fitted inside every CV fold. The effect is the biggest jump in the whole project. Structure alone gives 0.591; adding the region one-hot gives 0.672; and the target-encoded villages take us to 0.735, a gain of +6.3 pp from this one idea. Intuitively, the model now knows how badly each neighbourhood was hit, which is exactly the information an inspector would ask for first. Villages that never appear in training, 0.4% of the test set, simply receive the overall class mix.

### Slide 8: Highlight: ordinal vs multinomial (≈ 70 s)

Our second highlight tests whether the ordering of the damage grades can be exploited. A standard multinomial model treats grades 1, 2 and 3 as unrelated labels. Our ordinal version instead fits two binary logistic models: one for 'worse than grade 1' and one for 'worse than grade 2', then turns them into three class probabilities. Compared with the multinomial model on identical features, the ordinal approach changed micro-F1 by -0.06 pp and macro-F1 by -0.04 pp, so it made no real difference. This is a negative result, but an informative one: with only three classes the multinomial model is flexible enough to learn the ordering on its own. We also tried class weighting. It lowered macro-F1 by 0.88 pp and raised grade-1 recall from 0.47 to 0.83, but micro-F1 moved by -4.43 pp. Macro-F1 does not improve either, because many grade-2 buildings are now wrongly called grade 1, so grade-1 precision collapses. So weighting is a policy choice, not a free improvement.

*Hand over to Presenter 4.*

## Segment 4: Presenter 4 (slides 9–11, ≈ 2:35)

### Slide 9: Training and testing procedure (≈ 46 s)

Now, how we trained and tested. We split the labelled data 80 to 20, stratified by damage grade, and locked the 52,121-building holdout away until the very end. All comparisons and tuning used stratified five-fold cross-validation on the 80 percent, with every encoder re-fitted inside each fold. For logistic regression we ran seven experiments and tuned C on the best one, E4. The random forest and gradient boosting reuse the same features and folds, with small tuning grids. Each tuned model was scored once on the holdout, but the final model was chosen by cross-validation alone: HistGradientBoosting. It was then refit on all labelled data for our submission.

### Slide 10: Experimental results (≈ 52 s)

We start with model one. This chart shows cross-validated micro-F1 for every logistic-regression experiment, with error bars across the five folds. The majority baseline scores 0.569. Structure alone lifts this to 0.591, which is useful but modest. Adding the 31 regions gains +8.1 pp, and the target-encoded village levels add another +6.3 pp, the largest single step. Engineered features change micro-F1 by only +0.02 pp. The balanced and ordinal variants score 0.691 and 0.735. The fold-to-fold standard deviations are tiny, at most 0.19 percentage points, so the big steps are not noise. The lesson: building material matters, but only location tells a mud-stone house near the epicentre from one far away, and once location is in, hand-made features add almost nothing.

### Slide 11: Three-model comparison (≈ 57 s)

Now the comparison our course asked for: three models on exactly the same features and folds. Logistic regression reaches 0.735 cross-validated micro-F1 and 0.740 on the holdout. The random forest reaches 0.744 and 0.750, and HistGradientBoosting 0.745 and 0.750. So HistGradientBoosting is our final model, chosen on cross-validation only. Its gain over logistic regression is +0.98 pp in cross-validation and +0.93 pp on the holdout: real and consistent, but small. The trees can combine features by themselves, for example a material that is only dangerous where shaking was strong. The two tree models are practically tied: on the holdout the random forest is even +0.05 pp ahead, but we fixed in advance that cross-validation decides, so the holdout stays an honest check. Macro-F1 tells a similar story: 0.673, 0.687 and 0.694 in cross-validation.

*Hand over to Presenter 5.*

## Segment 5: Presenter 5 (slides 12–14, ≈ 2:26)

### Slide 12: Holdout performance (≈ 40 s)

Here is the final model, HistGradientBoosting, on the holdout. It scores a micro-F1 of 0.750 and a macro-F1 of 0.701, close to its cross-validated 0.745, so our model selection did not overfit. Grade 2 is recalled 85% of the time and grade 3 64%; grade 1 is hardest at 55%, because it is rare and often looks like grade 2. The grey numbers are logistic regression, for comparison. Importantly, mistakes are almost always between neighbouring grades: only 0.6% of destroyed buildings are mistaken for low damage, which is the costly error for inspectors.

### Slide 13: Prioritisation analysis (≈ 48 s)

This slide connects the models back to our problem statement. We ranked every holdout building by its predicted probability of grade 3 and asked: if inspectors work down this list, how many destroyed buildings do they find? With the final model, the top 10 percent finds 28% of all grade-3 buildings, the top 20 percent 51%, and the top 30 percent 67%, against 10, 20 and 30 percent for a random order. The three curves almost overlap: at 20 percent, logistic regression finds 49.8%, the forest 50.6% and boosting 50.6%. Concretely, in our holdout the first 5,212 visits would reach about 4,914 destroyed buildings, instead of about 1,744 in random order.

### Slide 14: Interpretation (≈ 59 s)

Why does a model call a building high-risk? On the left is logistic regression, which we can read directly: odds ratios for grade-3 damage, red raising and blue lowering the odds. The strongest risk factors are superstructure: mud mortar stone and age; the strongest protective ones are foundation type = i and roof type = x. Mud-mortar stone multiplies the odds of destruction by about 1.4, engineered reinforced concrete by 0.84. Tree ensembles have no coefficients, so on the right we use permutation importance: how much micro-F1 drops when we shuffle one input column. All three models rely first on location, then on construction details such as foundation, material and age, which matches our exploration and engineering intuition. The difference is that importance says how much a feature matters, while the odds ratios also say in which direction.

*Hand over to Presenter 6.*

## Segment 6: Presenter 6 (slides 15–16, ≈ 2:19)

### Slide 15: Summary of achievements (≈ 71 s)

To summarise. Our final model, HistGradientBoosting, reaches a holdout micro-F1 of 0.750, against 0.569 for always guessing grade 2. Translated into the problem statement, inspecting the top 20 percent of buildings on its list finds 51% of the destroyed ones. The biggest technical contribution was leakage-safe target encoding of village-level location, which helps every model. We compared three models fairly, and the trees beat logistic regression by +0.98 pp, so transparency costs a little accuracy but not much. We were strict about methodology: every transformation is inside one pipeline, so nothing is learned from validation data, and each tuned model saw the holdout exactly once. We also report the experiments that did not help, such as class weighting and the ordinal model, as honestly as the ones that did. Finally, the whole project, from the raw CSV files to the figures, the report and this deck, is reproducible with one command, and every number you have seen today is read automatically from a single results file.

### Slide 16: Future directions (≈ 68 s)

Finally, where would we go next? The most valuable addition would be measured ground shaking, for example peak ground acceleration from USGS ShakeMap, instead of letting region ids act as a proxy. Second, interaction terms such as material by region could close the gap between logistic regression and the trees while staying interpretable. Third, SHAP values would give the tree models per-building explanations, so the more accurate model could also tell an inspector why a building is flagged. A wider search, or libraries such as LightGBM or CatBoost, might add a little more accuracy. Fourth, decision thresholds should come from inspection capacity and from the cost of missing a destroyed building, and the probabilities should be calibrated so teams can trust the percentages. Lastly, before deploying a triage tool, we would test the model with spatially grouped cross-validation, to see how it performs in areas it has never seen. Thank you for listening; we are happy to take questions.
