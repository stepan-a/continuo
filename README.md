# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/stepan-a/continuo/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                       |    Stmts |     Miss |   Cover |   Missing |
|------------------------------------------- | -------: | -------: | ------: | --------: |
| src/continuo/\_\_init\_\_.py               |       11 |        0 |    100% |           |
| src/continuo/api.py                        |       45 |        0 |    100% |           |
| src/continuo/cli.py                        |       66 |        1 |     98% |       119 |
| src/continuo/codegen/\_\_init\_\_.py       |        6 |        0 |    100% |           |
| src/continuo/codegen/errors.py             |       12 |        0 |    100% |           |
| src/continuo/codegen/native.py             |       45 |        1 |     98% |        95 |
| src/continuo/codegen/residual.py           |       34 |        0 |    100% |           |
| src/continuo/codegen/translate.py          |      103 |        6 |     94% |186-187, 194, 216, 228, 238 |
| src/continuo/io/\_\_init\_\_.py            |        3 |        0 |    100% |           |
| src/continuo/io/solution.py                |       52 |        5 |     90% |70-71, 86, 98-99 |
| src/continuo/ir/\_\_init\_\_.py            |       11 |        0 |    100% |           |
| src/continuo/ir/boundary.py                |      105 |       11 |     90% |96, 103, 133, 141, 143, 146-149, 165, 192 |
| src/continuo/ir/build.py                   |       89 |        0 |    100% |           |
| src/continuo/ir/classify.py                |       81 |        5 |     94% |85, 87-88, 95, 97 |
| src/continuo/ir/commands.py                |      116 |        5 |     96% |106, 128, 156, 188, 225 |
| src/continuo/ir/errors.py                  |       12 |        0 |    100% |           |
| src/continuo/ir/model.py                   |       53 |        0 |    100% |           |
| src/continuo/ir/reduce.py                  |       85 |        3 |     96% |94, 101, 117 |
| src/continuo/ir/shocks.py                  |       66 |        1 |     98% |       108 |
| src/continuo/ir/steady\_state.py           |       40 |        0 |    100% |           |
| src/continuo/macro/\_\_init\_\_.py         |        5 |        0 |    100% |           |
| src/continuo/macro/eval.py                 |      565 |       27 |     95% |67, 304, 330, 357, 379, 391, 397, 401, 485, 532, 543, 549, 560, 565, 654, 765, 773, 788, 810, 828, 841, 875, 879, 883, 886-888 |
| src/continuo/macro/expand.py               |      347 |       12 |     97% |151, 159, 168, 210, 216, 225, 229, 353, 390, 412, 438, 453 |
| src/continuo/macro/lex.py                  |       49 |        1 |     98% |        77 |
| src/continuo/macro/linemap.py              |       31 |        0 |    100% |           |
| src/continuo/parser/\_\_init\_\_.py        |       19 |        0 |    100% |           |
| src/continuo/parser/ast.py                 |      130 |        0 |    100% |           |
| src/continuo/parser/errors.py              |        2 |        0 |    100% |           |
| src/continuo/parser/transform.py           |      126 |        0 |    100% |           |
| src/continuo/solve/\_\_init\_\_.py         |        9 |        0 |    100% |           |
| src/continuo/solve/\_klu.py                |      126 |       12 |     90% |82-85, 116-117, 171, 177, 187, 197, 209, 222 |
| src/continuo/solve/disc/\_\_init\_\_.py    |        4 |        0 |    100% |           |
| src/continuo/solve/disc/crank\_nicolson.py |       20 |        0 |    100% |           |
| src/continuo/solve/disc/grid.py            |       21 |        0 |    100% |           |
| src/continuo/solve/errors.py               |        3 |        0 |    100% |           |
| src/continuo/solve/linsolve.py             |      201 |       45 |     78% |226-227, 236, 245-248, 264-268, 271-278, 281, 284-286, 289, 292, 301-302, 319-321, 324-326, 329, 332, 335, 340-347, 352-359, 404, 406 |
| src/continuo/solve/numeric.py              |       23 |        4 |     83% |     38-41 |
| src/continuo/solve/orchestrator.py         |      109 |        2 |     98% |   263-264 |
| src/continuo/solve/pf.py                   |      197 |       15 |     92% |263, 308, 310, 330-333, 358-359, 422, 433-434, 436, 451, 456 |
| src/continuo/solve/rootfind.py             |      183 |       10 |     95% |102, 178, 187, 214, 266-267, 312, 329-330, 418 |
| src/continuo/solve/steady.py               |       85 |        0 |    100% |           |
| **TOTAL**                                  | **3290** |  **166** | **95%** |           |


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