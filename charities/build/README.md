# Religious charities graphic

Builds `charities/religion.html`, embedded on [charities.qmd](../../charities.qmd).

Source: Charities Regulator, Public Register of Charitable Organisations, effective date 26 October 2026, downloaded 30 October 2026. The register file (about 37 MB) is not kept in this repo.

    pip install pandas openpyxl numpy scipy
    python3 -I build_data.py path/to/public-register-of-charities.xlsx data.json
    python3 -I assemble.py template.html data.json ../religion.html

When you rebuild from a newer download, update the `downloaded` date in `build_data.py`.
