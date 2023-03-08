from pathlib import Path

from carder.carder import main

import click


@click.command()
@click.argument("template", type=click.Path(exists=True))
@click.argument("out", type=click.Path())
@click.option("--locale", default="")
@click.option("--repeat", default=1)
def run(template, out, locale, repeat):
    template_path = Path(template)
    out_path = Path(out)
    main(template_path, out_path, locale, repeat)


if __name__ == "__main__":
    run()
