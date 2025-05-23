import cherrypy
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource
from girder.constants import AccessType, SortDir, TokenScope
from girder.exceptions import RestException
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item

from dive_utils import constants

from . import crud, crud_dataset

DatasetModelParam = {
    'description': "dataset id",
    'model': Folder,
    'paramType': 'path',
    'required': True,
}


class SharableDatasetResource(Resource):
    """RESTful Sharable Dataset resource"""

    def __init__(self, resourceName):
        super(SharableDatasetResource, self).__init__()
        self.resourceName = resourceName

        def setUserAccessRequest(self, doc, user, level, save=False, flags=None, currentUser=None,
                      force=False):
            """
            Set user-level access on the resource.

            :param doc: The resource document to set access on.
            :type doc: dict
            :param user: The user to grant or remove access to.
            :type user: dict
            :param level: What level of access the user should have. Set to None
                to remove all access for this user.
            :type level: AccessType or None
            :param save: Whether to save the object to the database afterward.
                Set this to False if you want to wait to save the document for performance reasons.
            :type save: bool
            :param flags: List of access flags to grant to the group.
            :type flags: specific flag identifier, or a list/tuple/set of them
            :param currentUser: The user performing this action. Only required if attempting
                to set admin-only flags on the resource.
            :param force: Set this to True to set the flags regardless of the passed in
                currentUser's permissions (only matters if flags are passed).
            :type force: bool
            :returns: The modified resource document.
            """
            return self._setAccess(doc, user['_id'], 'requests', level, save, flags, currentUser, force)
        
        def hasAccessRequest(self, doc, user=None, level=AccessType.READ):
            if 'access' in doc:
                if self._hasUserAccess(doc['access'].get('requests', []),
                                        user['_id'], level):
                    return True
            return False

        Folder.setUserAccessRequest = setUserAccessRequest
        Folder.hasAccessRequest = hasAccessRequest

        Folder().exposeFields(AccessType.READ, "access")

        self.route("GET", (), self.list_datasets)
        self.route("PUT", (":id", 'request'), self.request_access)

    @access.user
    @autoDescribeRoute(
        Description("List datasets in the system")
        .pagingParams("created", defaultSortDir=SortDir.DESCENDING)
        .param(
            constants.PublishedMarker,
            'Return only published datasets',
            required=False,
            default=False,
            dataType='boolean',
        )
        .param(
            constants.SharedMarker,
            'Return only datasets shared with me',
            required=False,
            default=False,
            dataType='boolean',
        )
    )
    def list_datasets(
        self,
        limit: int,
        offset: int,
        sort,
        published: bool,
        shared: bool,
        requested: bool,
    ):
        return crud_dataset.list_datasets(
            self.getCurrentUser(),
            published,
            shared,
            requested,
            limit,
            offset,
            sort,
        )
        
    @access.user
    @autoDescribeRoute(
        Description("Request access to dataset")
        .modelParam(
            "id",
            level=AccessType.READ,
            **DatasetModelParam,
        )
    )
    def request_access(
        self,
        folder,
    ):
        return crud_dataset.request_access(
            folder,
            self.getCurrentUser(),
        )