# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/stepan-a/continuo/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                       |    Stmts |     Miss |   Cover |   Missing |
|------------------------------------------- | -------: | -------: | ------: | --------: |
| src/continuo/\_\_init\_\_.py               |       11 |        0 |    100% |           |
| src/continuo/api.py                        |       41 |        0 |    100% |           |
| src/continuo/cli.py                        |       74 |        4 |     95% |57-59, 147 |
| src/continuo/codegen/\_\_init\_\_.py       |        6 |        0 |    100% |           |
| src/continuo/codegen/errors.py             |       12 |        0 |    100% |           |
| src/continuo/codegen/native.py             |       45 |        1 |     98% |       102 |
| src/continuo/codegen/residual.py           |       51 |        2 |     96% |     91-92 |
| src/continuo/codegen/translate.py          |      103 |        6 |     94% |186-187, 194, 216, 228, 238 |
| src/continuo/io/\_\_init\_\_.py            |        3 |        0 |    100% |           |
| src/continuo/io/solution.py                |       52 |        5 |     90% |70-71, 86, 98-99 |
| src/continuo/ir/\_\_init\_\_.py            |       12 |        0 |    100% |           |
| src/continuo/ir/\_exprtools.py             |       27 |        3 |     89% | 41, 43-44 |
| src/continuo/ir/boundary.py                |      100 |       11 |     89% |95, 102, 132, 140, 142, 145-148, 164, 191 |
| src/continuo/ir/build.py                   |       91 |        0 |    100% |           |
| src/continuo/ir/classify.py                |       66 |        2 |     97% |    74, 76 |
| src/continuo/ir/commands.py                |      153 |        5 |     97% |133, 184, 205, 283, 320 |
| src/continuo/ir/constraints.py             |       37 |        1 |     97% |        45 |
| src/continuo/ir/errors.py                  |       12 |        0 |    100% |           |
| src/continuo/ir/model.py                   |       71 |        0 |    100% |           |
| src/continuo/ir/reduce.py                  |       88 |        3 |     97% |98, 105, 121 |
| src/continuo/ir/shocks.py                  |       61 |        0 |    100% |           |
| src/continuo/ir/steady\_state.py           |       39 |        0 |    100% |           |
| src/continuo/macro/\_\_init\_\_.py         |        5 |        0 |    100% |           |
| src/continuo/macro/eval.py                 |      565 |       27 |     95% |67, 304, 330, 357, 379, 391, 397, 401, 485, 532, 543, 549, 560, 565, 654, 765, 773, 788, 810, 828, 841, 875, 879, 883, 886-888 |
| src/continuo/macro/expand.py               |      347 |       12 |     97% |151, 159, 168, 210, 216, 225, 229, 353, 390, 412, 438, 453 |
| src/continuo/macro/lex.py                  |       49 |        1 |     98% |        77 |
| src/continuo/macro/linemap.py              |       31 |        0 |    100% |           |
| src/continuo/parser/\_\_init\_\_.py        |       19 |        0 |    100% |           |
| src/continuo/parser/ast.py                 |      131 |        0 |    100% |           |
| src/continuo/parser/errors.py              |        2 |        0 |    100% |           |
| src/continuo/parser/transform.py           |      163 |        0 |    100% |           |
| src/continuo/solve/\_\_init\_\_.py         |        9 |        0 |    100% |           |
| src/continuo/solve/\_klu.py                |      126 |       12 |     90% |82-85, 116-117, 171, 177, 187, 197, 209, 222 |
| src/continuo/solve/disc/\_\_init\_\_.py    |        8 |        0 |    100% |           |
| src/continuo/solve/disc/collocation.py     |       39 |        0 |    100% |           |
| src/continuo/solve/disc/crank\_nicolson.py |       20 |        0 |    100% |           |
| src/continuo/solve/disc/grid.py            |       44 |        0 |    100% |           |
| src/continuo/solve/disc/monitor.py         |       94 |        3 |     97% |118, 173, 190 |
| src/continuo/solve/disc/tableaux.py        |       49 |        1 |     98% |       124 |
| src/continuo/solve/errors.py               |        3 |        0 |    100% |           |
| src/continuo/solve/linsolve.py             |      206 |       46 |     78% |233-234, 243, 252-255, 271-275, 278-285, 288, 291-293, 296, 299, 308-309, 326-328, 331-333, 336, 339, 342, 345, 350-357, 362-369, 414, 416 |
| src/continuo/solve/numeric.py              |       23 |        4 |     83% |     38-41 |
| src/continuo/solve/orchestrator.py         |      120 |        2 |     98% |   353-354 |
| src/continuo/solve/pf.py                   |      242 |       15 |     94% |391, 398, 403, 423-426, 455-456, 543, 554-555, 557, 572, 577 |
| src/continuo/solve/refine.py               |       73 |        1 |     99% |       198 |
| src/continuo/solve/rootfind.py             |      185 |       11 |     94% |102, 178, 187, 214, 266-268, 315, 332-334 |
| src/continuo/solve/steady.py               |      125 |        0 |    100% |           |
| src/continuo/solve/transform.py            |       92 |        0 |    100% |           |
| **TOTAL**                                  | **3925** |  **178** | **95%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/stepan-a/continuo/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/stepan-a/continuo/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/stepan-a/continuo/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/stepan-a/continuo/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fstepan-a%2Fcontinuo%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/stepan-a/continuo/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.