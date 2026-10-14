import sys

from airbyte_cdk.entrypoint import launch

from source_facebook_organic import SourceFacebookOrganic

if __name__ == "__main__":
    launch(SourceFacebookOrganic(), sys.argv[1:])
