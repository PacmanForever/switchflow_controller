# Home Assistant Brands PR Notes

This integration can already ship its own brand assets locally in:

`custom_components/switchflow_controller/brand/`

That is the current official route for custom integrations.

Important policy note:

- The current `home-assistant/brands` pull request template states that pull requests for adding new custom components are no longer accepted.
- That means a new PR for `switchflow_controller` under `custom_integrations/` is likely to be closed, even if the images themselves are valid.

## Legacy repository layout

If you still want to prepare the legacy submission structure, the folder in `home-assistant/brands` would be:

```text
custom_integrations/switchflow_controller/
├── icon.png
└── icon@2x.png
```

We are intentionally using a single square image family.

- `icon.png`: 256x256
- `icon@2x.png`: 512x512
- No separate logo files required if the square icon should also be used as logo fallback.

Source files in this repository:

- `custom_components/switchflow_controller/brand/icon.png`
- `custom_components/switchflow_controller/brand/icon@2x.png`

## PR text draft

The template in `home-assistant/brands` is written for core integrations, so none of the checkboxes perfectly match a new custom integration submission anymore. If you still open a PR for discussion, this is the cleanest possible draft:

```md
## Proposed change

Add brand images for the custom integration `switchflow_controller`.

The assets use a single square icon family centered on a smart wall switch motif,
which matches the integration's purpose more clearly than a generic abstract symbol.

Files included:

- `custom_integrations/switchflow_controller/icon.png`
- `custom_integrations/switchflow_controller/icon@2x.png`

The same square image is intended to serve as both icon and logo fallback.

## Type of change

- [ ] Add a new logo or icon for a new core integration
- [ ] Add a missing icon or logo for an existing core integration
- [ ] Replace an existing icon or logo with a higher quality version
- [ ] Replace an existing icon or logo after a branding change
- [ ] Removing an icon or logo

## Additional information

- This PR fixes or closes issue: fixes #
- Link to code base pull request: 
- Link to documentation pull request: 
- Link to integration documentation on our website: 

## Checklist

- [x] The added/replaced image(s) are **PNG**
- [x] Icon image size is 256x256px (`icon.png`)
- [x] hDPI icon image size is 512x512px for (`icon@2x.png`)
- [ ] Logo image size has min 128px, but max 256px, on the shortest side (`logo.png`)
- [ ] hDPI logo image size has min 256px, but max 512px, on the shortest side (`logo@2x.png`)
```

## Practical recommendation

For this project, rely on the local brand directory already present in the integration.

If you still want central listing for historical reasons, open the PR knowing that:

- the folder path would be `custom_integrations/switchflow_controller/`
- the two files above are sufficient for a single-image setup
- acceptance is unlikely because new custom integration brand PRs are no longer the preferred workflow
