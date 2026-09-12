# Phase 7C deployment trigger

Pushes to `master` are deployed by the SnapDeploy GitHub integration through the existing `scholarzone-api-2ee2d` container. The repository workflow only verifies the deployed container; it does not call the SnapDeploy API or require `SNAPDEPLOY_API_KEY`.

The SnapDeploy container must remain linked to `gopal735/ScholarZone`, branch `master`, with Auto Deploy on Push enabled.
