# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ament_copyright.main import main
from conftest import lint_paths
import pytest


@pytest.mark.copyright
@pytest.mark.linter
def test_copyright():
    # coco_schemas/gen/ is protoc's output: excluded (conftest.lint_paths).
    rc = main(argv=lint_paths())
    assert rc == 0, 'Found errors'
