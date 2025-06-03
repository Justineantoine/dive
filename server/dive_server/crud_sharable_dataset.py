import math
from numpy import linspace
from typing import List, Tuple

import cherrypy
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.file import File

from dive_server import crud, crud_annotation, crud_dataset
from dive_utils import constants, fromMeta, models, types

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

def list_requested_datasets(
    user: types.GirderUserModel,
    limit: int,
    offset: int,
    sortParams: Tuple[Tuple[str, int]],
):
    sort, sortDir = (sortParams or [['created', 1]])[0]
    pipeline = get_requested_dataset_query(user)

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
                            'localField': 'sharableFolder.access.requests.id',
                            'foreignField': '_id',
                            'as': 'requestingUser',
                        },
                    },
                    {'$unwind': '$requestingUser'},
                ],
                'totalCount': [{'$count': 'count'}],
            },
        },
    ]

    response = next(Folder().collection.aggregate(pipeline))
    total = response['totalCount'][0]['count'] if response['totalCount'] else 0
    cherrypy.response.headers['Girder-Total-Count'] = total
    return [Folder().filter(doc, additionalKeys=['requestingUser', 'sharableFolder']) for doc in response['results']]


def share_dataset(
    dsFolder: types.GirderModel, user: types.GirderUserModel, share: bool
) -> str:
    if dsFolder['public']:
        return {
            'message': 'Public datasets cannot be shared',
        }
    Folder().requireAccess(dsFolder, user, level=AccessType.ADMIN)
    crud.verify_dataset(dsFolder)
    sharable_folder_name = dsFolder['name']+'_shared'
    sharable_dataset_folder = Folder().findOne(
        {
            'name': sharable_folder_name,
            'parentId': dsFolder['parentId'],
        }
    )
    if sharable_dataset_folder is not None:
        Folder().remove(sharable_dataset_folder)

    if share:
        parent_folder = Folder().findOne({'_id': dsFolder['parentId']})
        dataset_type = fromMeta(dsFolder, constants.TypeMarker)
        if dataset_type not in [constants.ImageSequenceType, constants.LargeImageType]:
            return {
                'message': 'Dataset type not suitable for sharing',
            }
        
        def set_preview_frames(frames):
            n_preview_frames =  math.ceil(0.2 * len(frames))
            return linspace(0, len(frames) - 1, n_preview_frames, dtype=int).tolist()

        sharable_dataset_folder = Folder().createFolder(
            parent=parent_folder,
            name=sharable_folder_name,
            parentType=dsFolder['parentCollection'],
            creator=user,
            public=True,
        )
        sharable_dataset_folder['meta'].update(dsFolder['meta'])
        sharable_dataset_folder['size'] = dsFolder['size']
        crud.get_or_create_auxiliary_folder(sharable_dataset_folder, user)
        crud_annotation.clone_annotations(dsFolder, sharable_dataset_folder, user)
        
        frames = (
            crud.valid_images(dsFolder, user)
            if dataset_type == constants.ImageSequenceType
            else crud.valid_large_images(dsFolder, user)
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
            constants.OriginalDatasetName: dsFolder['name'],
        })
        Folder().save(sharable_dataset_folder)
        crud_dataset.update_metadata(dsFolder, { constants.SharableMediaIdMarker: sharable_dataset_folder['_id'] })

        return {
            'message': 'Dataset sharable',
        }
    else:
        crud_dataset.update_metadata(dsFolder, { constants.SharableMediaIdMarker: '' })
        return {
            'message': 'Dataset unsharable',
        }


def request_access(
    dsFolder: types.GirderModel, user: types.GirderUserModel
) -> str:
    crud.verify_dataset(dsFolder)
    if dsFolder['creatorId'] == user['_id'] or user['admin']:
        return {
            'message': 'User already has access to this data',
        }
    elif Folder().hasRequestedAccess(dsFolder, user, status=['pending', 'granted']):
        return {
            'message': 'User has already requested access to this data',
        }
    Folder().setUserAccessRequest(dsFolder, user)

    return {
        'message': 'Access request sent',
    }


def grant_access(
    dsFolder: types.GirderModel, user: types.GirderUserModel, request_user: str, grant: bool
):
    Folder().requireAccess(dsFolder, user, level=AccessType.ADMIN)
    sharable_folder = Folder().findOne({'_id': fromMeta(dsFolder, constants.SharableMediaIdMarker)})
    if grant:
        Folder().setUserAccess(dsFolder, request_user, level=AccessType.READ, save=True)
        Folder().setUserAccessRequest(
            sharable_folder, request_user, status='granted'
        )
    else:
        Folder().setUserAccessRequest(
            sharable_folder, request_user, status='refused'
        )


def get_media(
    dsFolder: types.GirderModel, user: types.GirderUserModel
) -> models.DatasetSourceMedia:
    imageData: List[models.MediaResource] = []
    crud.verify_sharable_dataset(dsFolder)
    source_type = fromMeta(dsFolder, constants.TypeMarker)
    preview_frames = fromMeta(dsFolder, constants.PreviewFrames)
    print(f'Source Type: {source_type}')
    
    if source_type == constants.ImageSequenceType:
        imageData = [
            models.MediaResource(
                id=str(image['_id']) if index in preview_frames else '',
                url=get_url(dsFolder, image, preview=index in preview_frames),
                filename=image['name'],
            )
            for index, image in enumerate(crud.valid_images(dsFolder, user))
        ]

    elif source_type == constants.LargeImageType:
        imageData = [
            models.MediaResource(
                id=str(image['_id']) if index in preview_frames else '',
                url=get_large_image_metadata_url(image, modelType='item', preview=index in preview_frames),
                filename=image['name'],
            )
            for index, image in enumerate(crud.valid_large_images(dsFolder, user))
        ]

    else:
        raise ValueError(f'Unrecognized source type: {source_type}')

    return models.DatasetSourceMedia(
        imageData=imageData
    )


def get_sharable_dataset_query(
    user: types.GirderUserModel
):
    return {
        '$and': [
            # Find datasets
            {'meta.annotate': True},
            # not owned by the current user
            {'$nor': [{'creatorId': {'$eq': user['_id']}}, {'creatorId': {'$eq': None}}]},
            # But marked as sharable
            {f'meta.{constants.SharableMarker}': True},
        ]
    }


def get_requested_dataset_query(
    user: types.GirderUserModel
):
    return [
        {
            '$match': {
                '$and': [
                    {'creatorId': {'$eq': user['_id']}},
                    {f'meta.{constants.SharableMediaIdMarker}': { '$exists': True, '$ne': ''}},
                ],
            },
        },
        {
            '$lookup': {
                'from': 'folder',
                'localField': f'meta.{constants.SharableMediaIdMarker}',
                'foreignField': '_id',
                'as': 'sharableFolder'
            },
        },
        {'$unwind': '$sharableFolder'},
        {'$unwind': '$sharableFolder.access.requests'},
        {'$match': {'sharableFolder.access.requests.status': {'$eq': 'pending'}}},
    ]
