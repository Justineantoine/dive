from enum import Enum
import math
from numpy import linspace
from typing import List, Tuple

import cherrypy
from girder import events
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.file import File

from dive_server import crud, crud_annotation
from dive_utils import constants, fromMeta, models, types


class RequestStatus(Enum):
    GRANTED = 'granted'
    DENIED = 'denied'
    PENDING = 'pending'


def get_url(
    dataset: types.GirderModel,
    item: types.GirderModel,
    preview: bool,
) -> str:
    return f"/api/v1/dive_dataset/{str(dataset['_id'])}/media/{str(item['_id'])}/download" if preview else ''


def get_large_image_metadata_url(
    file: types.GirderModel,
    modelType='item',
    preview = False,
) -> str:
    return f"api/v1/{modelType}/{str(file['_id'])}/tiles/internal_metadata" if preview else ''


def list_sharable_datasets(
    user: types.GirderUserModel,
    limit: int,
    offset: int,
    sortParams: Tuple[Tuple[str, int]],
):
    sort, sortDir = (sortParams or [['created', 1]])[0]
    pipeline = [{'$match': get_sharable_dataset_query(user)}]

    pipeline += [
        {
            '$facet': {
                'results': [
                    {'$sort': {sort: sortDir}},
                    {'$skip': offset},
                    {'$limit': limit},
                    {
                        '$lookup': {
                            'from': 'user',
                            'localField': 'creatorId',
                            'foreignField': '_id',
                            'as': 'ownerLogin',
                        },
                    },
                    {'$set': {'ownerLogin': {'$first': '$ownerLogin'}}},
                    {'$set': {'ownerLogin': '$ownerLogin.login'}},
                ],
                'totalCount': [{'$count': 'count'}],
            },
        },
    ]

    response = next(Folder().collection.aggregate(pipeline))
    total = response['totalCount'][0]['count'] if response['totalCount'] else 0
    cherrypy.response.headers['Girder-Total-Count'] = total
    return [Folder().filter(doc, additionalKeys=['ownerLogin']) for doc in response['results']]

def list_dataset_requests(
    user: types.GirderUserModel,
    limit: int,
    offset: int,
    sortParams: Tuple[Tuple[str, int]],
):
    sort, sortDir = (sortParams or [['created', 1]])[0]
    pipeline = get_dataset_requests_query(user)

    pipeline += [
        {
            '$facet': {
                'results': [
                    {'$sort': {sort: sortDir}},
                    {'$skip': offset},
                    {'$limit': limit},
                    {
                        '$lookup': {
                            'from': 'user',
                            'localField': 'access.requests.id',
                            'foreignField': '_id',
                            'as': 'requestingUser',
                        },
                    },
                    {'$set': {'requestingUserLogin': {'$first': '$requestingUser'}}},
                    {'$set': {'requestingUserLogin': '$requestingUser.login'}},
                    {'$unwind': '$requestingUserLogin'},
                ],
                'totalCount': [{'$count': 'count'}],
            },
        },
    ]

    response = next(Folder().collection.aggregate(pipeline))
    total = response['totalCount'][0]['count'] if response['totalCount'] else 0
    cherrypy.response.headers['Girder-Total-Count'] = total
    return [Folder().filter(doc, additionalKeys=['requestingUserLogin']) for doc in response['results']]


def share_dataset(
    folder: types.GirderModel, user: types.GirderUserModel, share: bool
) -> str:
    if folder['public']:
        return {
            'message': 'Public datasets cannot be shared',
        }
    Folder().requireAccess(folder, user, level=AccessType.ADMIN)
    crud.verify_dataset(folder)
    sharable_folder_name = folder['name']+'_shared'
    sharable_dataset_folder = Folder().findOne(
        {
            'name': sharable_folder_name,
            'parentId': folder['parentId'],
        }
    )
    if sharable_dataset_folder is not None:
        Folder().remove(sharable_dataset_folder)

    if share:
        parent_folder = Folder().findOne({'_id': folder['parentId']})
        dataset_type = fromMeta(folder, constants.TypeMarker)
        if dataset_type not in [constants.ImageSequenceType, constants.LargeImageType]:
            return {
                'message': 'Dataset type not suitable for sharing',
            }
        
        def set_preview_frames(frames):
            n_preview_frames =  math.ceil(0.05 * len(frames))
            return linspace(0, len(frames) - 1, n_preview_frames, dtype=int).tolist()

        sharable_dataset_folder = Folder().createFolder(
            parent=parent_folder,
            name=sharable_folder_name,
            parentType=folder['parentCollection'],
            creator=user,
            public=True,
        )
        sharable_dataset_folder['meta'].update(folder['meta'])
        sharable_dataset_folder['size'] = folder['size']
        crud.get_or_create_auxiliary_folder(sharable_dataset_folder, user)
        crud_annotation.clone_annotations(folder, sharable_dataset_folder, user)
        
        frames = (
            crud.valid_images(folder, user)
            if dataset_type == constants.ImageSequenceType
            else crud.valid_large_images(folder, user)
        )
        preview_frames = set_preview_frames(frames)

        for index, frame in enumerate(frames):
            is_previewable = index in preview_frames

            new_item = Item().createItem(
                name=frame['name'],
                creator=user,
                folder=sharable_dataset_folder,
                description=frame.get('description', ''),
                reuseExisting=False
            )

            if 'meta' in frame:
                new_item['meta'] = frame['meta']
                new_item = Item().save(new_item)
            
            if is_previewable:
                for file in File().find({'itemId': frame['_id']}):
                    File().copyFile(file, user, new_item)

        sharable_dataset_folder['meta'].update({
            constants.SharableMarker: True ,
            constants.PreviewFrames: preview_frames,
            constants.OriginalMediaName: folder["name"]

        })
        sharable_dataset_folder[constants.OriginalMediaId] = folder["_id"]
        Folder().save(sharable_dataset_folder)
        folder[constants.SharableMediaId] = sharable_dataset_folder["_id"]
        Folder().save(folder)

        return {
            'message': 'Sharable dataset created',
        }
    else:
        del folder[constants.SharableMediaId]
        Folder().save(folder)
        return {
            'message': 'Sharable dataset removed',
        }


def request_access(
    folder: types.GirderModel, user: types.GirderUserModel
) -> str:
    crud.verify_dataset(folder)
    if folder['creatorId'] == user['_id']:
        return {
            'message': 'User already has access to this data',
        }
    elif Folder().hasRequestedAccess(folder, user, status=[RequestStatus.GRANTED.value, RequestStatus.PENDING.value]):
        return {
            'message': 'User has already requested access to this data',
        }
    Folder().setUserAccessRequest(folder, user)
    events.trigger('access_request', {
        'user': user,
        'dataset': folder
    })

    return {
        'message': 'Access request sent',
    }


def grant_access(
    sharable_folder: types.GirderModel,
    folder_owner: types.GirderUserModel,
    sharable_exchange_folder: types.GirderUserModel,
    exchange_folder_owner: types.GirderUserModel,
):
    # Check Access rights to sharable folders
    Folder().requireAccess(sharable_folder, folder_owner, level=AccessType.ADMIN)
    Folder().requireAccess(sharable_exchange_folder, exchange_folder_owner, level=AccessType.ADMIN)

    # Give access to requesting user
    folder = Folder().findOne({'_id': sharable_folder.get(constants.OriginalMediaId)})
    Folder().requireAccess(folder, folder_owner, level=AccessType.ADMIN)
    Folder().setUserAccess(
        folder, exchange_folder_owner, level=AccessType.READ, save=True
    )

    # Give access to the requested user
    exchange_folder = Folder().findOne({'_id': sharable_exchange_folder.get(constants.OriginalMediaId)})
    Folder().requireAccess(exchange_folder, exchange_folder_owner, level=AccessType.ADMIN)
    Folder().setUserAccess(
        exchange_folder, folder_owner, level=AccessType.READ, save=True
    )

    # Update requests on sharable folders
    Folder().setUserAccessRequest(
        sharable_folder, exchange_folder_owner, status=RequestStatus.GRANTED
    )
    Folder().setUserAccessRequest(
        sharable_exchange_folder, folder_owner, status=RequestStatus.GRANTED
    )
    events.trigger('access_granted', {
        'dataset': sharable_folder,
        'dataset_owner': folder_owner,
        'exchange_dataset': sharable_exchange_folder,
        'exchange_dataset_owner': exchange_folder_owner,
    })


def deny_access(
    sharable_folder: types.GirderModel,
    owner: types.GirderUserModel,
    requesting_user: types.GirderUserModel,
):
    Folder().requireAccess(sharable_folder, owner, level=AccessType.ADMIN)
    Folder().setUserAccessRequest(
        sharable_folder, requesting_user, status=RequestStatus.DENIED
    )
    events.trigger('access_denied', {
        'dataset': sharable_folder,
        'dataset_owner': owner,
        'requesting_user': requesting_user,
    })


def get_media(
    folder: types.GirderModel, user: types.GirderUserModel
) -> models.DatasetSourceMedia:
    imageData: List[models.MediaResource] = []
    crud.verify_sharable_dataset(folder)
    source_type = fromMeta(folder, constants.TypeMarker)
    preview_frames = fromMeta(folder, constants.PreviewFrames)
    print(f'Source Type: {source_type}')
    
    if source_type == constants.ImageSequenceType:
        imageData = [
            models.MediaResource(
                id=str(image['_id']) if index in preview_frames else '',
                url=get_url(folder, image, preview=index in preview_frames),
                filename=image['name'],
            )
            for index, image in enumerate(crud.valid_images(folder, user))
        ]

    elif source_type == constants.LargeImageType:
        imageData = [
            models.MediaResource(
                id=str(image['_id']) if index in preview_frames else '',
                url=get_large_image_metadata_url(image, modelType='item', preview=index in preview_frames),
                filename=image['name'],
            )
            for index, image in enumerate(crud.valid_large_images(folder, user))
        ]

    else:
        raise ValueError(f'Unrecognized source type: {source_type}')

    return models.DatasetSourceMedia(
        imageData=imageData
    )


def get_sharable_dataset_query(
    user: types.GirderUserModel,
):
    return {
        '$and': [
            # Find datasets
            {'meta.annotate': True},
            # not owned by the current user
            {'$nor': [{'creatorId': {'$eq': user['_id']}}, {'creatorId': {'$eq': None}}]},
            # But marked as sharable
            {f'meta.{constants.SharableMarker}': True},
            {'access.requests': { '$not': { '$elemMatch':
                {
                    'id': user['_id'],
                    'status': RequestStatus.GRANTED.value
                }
            }}}
        ]
    }


def get_dataset_requests_query(
    user: types.GirderUserModel
):
    return [
        {
            '$match': {
                '$and': [
                    {'meta.annotate': True},
                    {'creatorId': {'$eq': user['_id']}},
                    {f'meta.{constants.SharableMarker}': True},
                ]
            },
        },
        {'$unwind': '$access.requests'},
        {'$match': {'access.requests.status': {'$eq': RequestStatus.PENDING.value}}},
    ]
