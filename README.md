# NeuralFight

A website that predicts who will win UFC fights, and how, using a model trained on past fight statistics.

NeuralFight collects the results and round-by-round stats of every past UFC event (strikes landed, takedowns, time spent in control, and so on) along with each fighter's height, reach, and age. A machine-learning model (a program that learns patterns from past examples) uses that history to estimate each fighter's chance of winning and whether the fight is likely to end by knockout, submission, or the judges' decision. It also compares its estimates with betting odds to point out fights where the two disagree.

It is a personal project made out of curiosity about the sport and about prediction. The predictions are for interest only and are not betting advice.

## What you can do with it

- Browse upcoming and past UFC events and see a predicted winner and win chance for each fight.
- Open a fight to see the predicted way it ends and a short written reason behind the pick.
- Look up any fighter's page and record.
- See "upsets": fights where the model favours the fighter the betting market expects to lose.
- Check how accurate the model has been on past fights, broken down by confidence and by how fights ended.
- Try a parlay builder (combining several fight picks into one) and view a history of the model's suggested bets.

## Try it

https://neural-fight.vercel.app
