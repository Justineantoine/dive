"""adds functionality to existing girder views"""

import types
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import boundHandler, Resource, filtermodel
from girder.constants import AccessType, SortDir
from girder.models.user import User
from girder.models.folder import Folder
from girder_jobs.models import job
from girder_worker.utils import JobStatus

from dive_utils import constants

from . import crud_override

@access.user
@boundHandler
@autoDescribeRoute(
    Description('Set user use private queue')
    .modelParam("id", description='user id', model=User, level=AccessType.ADMIN)
    .param(
        "privateQueueEnabled",
        description="Set private queue enabled",
        paramType='query',
        dataType='boolean',
        default=None,
    )
)
def use_private_queue(self, user: dict, privateQueueEnabled: bool):
    if privateQueueEnabled is not None:
        user[constants.UserPrivateQueueEnabledMarker] = privateQueueEnabled
        User().save(user)
    return {
        constants.UserPrivateQueueEnabledMarker: user.get(
            constants.UserPrivateQueueEnabledMarker, False
        ),
    }


@access.user
@boundHandler
@autoDescribeRoute(Description('Get number of outstanding jobs'))
def countJobs(self):
    outstanding = (
        job.Job()
        .find(
            {
                "status": {
                    "$in": [
                        JobStatus.INACTIVE,
                        JobStatus.QUEUED,
                        JobStatus.RUNNING,
                        JobStatus.CANCELING,
                        JobStatus.CONVERTING_INPUT,
                        JobStatus.CONVERTING_OUTPUT,
                        JobStatus.FETCHING_INPUT,
                        JobStatus.PUSHING_OUTPUT,
                    ]
                }
            }
        )
        .count()
    )

    return {
        'outstanding': outstanding,
    }

@access.user
@autoDescribeRoute(
    Description("List shared folders to the user.")
    .pagingParams("created", defaultSortDir=SortDir.DESCENDING)
    .param(
        "onlyNonAccessibles",
        "Returns only folder that are shared with the user but are under a private directory",
        paramType="query",
        dataType="boolean",
        default=True,
        required=False,
    )
)
def list_shared_folders(
    limit: int,
    offset: int,
    sort,
    onlyNonAccessibles: bool
):
    return crud_override.list_shared_folders(
        Resource().getCurrentUser(),
        limit,
        offset,
        sort,
        onlyNonAccessibles
    )

@access.user
@autoDescribeRoute(
    Description("Get the path to the root, or closest shared parent, of the folder's hierarchy.")
    .modelParam("id", model=Folder, level=AccessType.READ)
    .errorResponse('ID was invalid.')
    .errorResponse('Read access was denied for the folder.', 403)
)
def get_root_path_or_relative(folder):
    return crud_override.get_root_path_or_relative(
        Resource().getCurrentUser(),
        folder
    )

@access.public()
@filtermodel(model=Folder)
@autoDescribeRoute(
    Description('Search for folders by certain properties.')
    .notes('You must pass either a "folderId" or "text" field '
        'to specify how you are searching for folders.  '
        'If you omit one of these parameters the request will fail and respond : '
        '"Invalid search mode."')
    .responseClass('Folder', array=True)
    .param('parentType', "Type of the folder's parent", required=False,
        enum=['folder', 'user', 'collection'])
    .param('parentId', "The ID of the folder's parent.", required=False)
    .param('text', 'Pass to perform a text search.', required=False)
    .param('name', 'Pass to lookup a folder by exact name match. Must '
        'pass parentType and parentId as well when using this.', required=False)
    .pagingParams(defaultSort='lowerName')
    .errorResponse()
    .errorResponse('Read access was denied on the parent resource.', 403)
)
def find(parentType, parentId, text, name, limit, offset, sort):
    user = Resource().getCurrentUser()
    return crud_override.find(user, parentType, parentId, text, name, limit, offset, sort)