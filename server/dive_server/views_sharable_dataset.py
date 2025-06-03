from bson.objectid import ObjectId

from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource
from girder.constants import AccessType, SortDir
from girder.models.folder import Folder
from girder.models.user import User

from . import crud_sharable_dataset

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

        def setUserAccessRequest(self, doc, user, status='pending'):
            id = user['_id']
            if not isinstance(id, ObjectId):
                id = ObjectId(id)

            if 'access' not in doc:
                doc['access'] = {'requests': []}

            key = 'access.requests'
            update = {}
            entry = {
                'id': id,
                'status': status
            }

            for index, perm in enumerate(doc['access']['requests']):
                if perm['id'] == id:
                    # if the id already exists we want to update with a $set
                    doc['access']['requests'][index] = entry
                    update['$set'] = {'%s.%s' % (key, index): entry}
                    break
            else:
                doc['access']['requests'].append(entry)
                update['$push'] = {key: entry}

            doc = self._saveAcl(doc, update)
            return doc
        
        def hasRequestedAccess(self, doc, user=None, status=None):
            if status is not None and not isinstance(status, list):
                status = [status]
            if 'access' in doc:
                for userRequest in doc['access'].get('requests', []):
                    if (userRequest['id'] == user['_id'] and
                        (status is None or userRequest['status'] in status)):
                        return True if status is not None else userRequest['status']
                return False if status is not None else None

        Folder.setUserAccessRequest = setUserAccessRequest
        Folder.hasRequestedAccess = hasRequestedAccess

        self.route("GET", (), self.list_datasets)
        self.route("GET", ("requests",), self.list_requested_datasets)
        self.route("GET", (":id", "media"), self.get_media)
        self.route("POST", (":id", "share"), self.share_dataset)
        self.route("PUT", (":id", 'requested'), self.has_requested)
        self.route("PUT", (":id", 'request-access'), self.request_access)
        self.route("PUT", (":id", 'grant-access'), self.grant_access)

    @access.user
    @autoDescribeRoute(
        Description("List sharable datasets in the system")
        .pagingParams("created", defaultSortDir=SortDir.DESCENDING)
    )
    def list_datasets(
        self,
        limit: int,
        offset: int,
        sort,
    ):
        return crud_sharable_dataset.list_sharable_datasets(
            self.getCurrentUser(),
            limit,
            offset,
            sort,
        )

    @access.user
    @autoDescribeRoute(
        Description("List datasets requests")
        .pagingParams("created", defaultSortDir=SortDir.DESCENDING)
    )
    def list_requested_datasets(
        self,
        limit: int,
        offset: int,
        sort,
    ):
        return crud_sharable_dataset.list_requested_datasets(
            self.getCurrentUser(),
            limit,
            offset,
            sort,
        )

    @access.user
    @autoDescribeRoute(
        Description("Get dataset source media").modelParam(
            "id", level=AccessType.READ, **DatasetModelParam
        )
    )
    def get_media(self, folder):
        return crud_sharable_dataset.get_media(folder, self.getCurrentUser()).dict(exclude_none=True)

    @access.user
    @autoDescribeRoute(
        Description("Share/Unshare data to other users")
        .modelParam(
            "id", level=AccessType.READ, **DatasetModelParam
        )
        .param(
            "share",
            "Share data",
            paramType="query",
            dataType="boolean",
        )
    )
    def share_dataset(self, folder, share):
        return crud_sharable_dataset.share_dataset(folder, self.getCurrentUser(), share)

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
        return crud_sharable_dataset.request_access(
            folder,
            self.getCurrentUser(),
        )

    @access.user
    @autoDescribeRoute(
        Description("Grant access to dataset")
        .modelParam(
            "id",
            level=AccessType.READ,
            **DatasetModelParam,
        )
        .param(
            "userId",
            "User requesting access",
            paramType="query",
            dataType="string",
        )
        .param(
            "grant",
            "Grant access",
            paramType="query",
            dataType="boolean",
        )
    )
    def grant_access(
        self,
        folder,
        userId,
        grant,
    ):
        request_user = User().findOne({'_id': ObjectId(userId)})
        return crud_sharable_dataset.grant_access(
            folder,
            self.getCurrentUser(),
            request_user,
            grant,
        )

    @access.user
    @autoDescribeRoute(
        Description("Grant access to dataset")
        .modelParam(
            "id",
            level=AccessType.READ,
            **DatasetModelParam,
        )
    )
    def has_requested(
        self,
        folder,
    ):
        user = self.getCurrentUser()
        request_status = Folder().hasRequestedAccess(folder, user)
        return {"id": user["_id"], "status": request_status}
