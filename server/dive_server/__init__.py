import os
from pathlib import Path

from girder import events, plugin
from girder.constants import AccessType
from girder.models.setting import Setting
from girder.models.user import User
from girder.models.folder import Folder
from girder.models.collection import Collection
from girder.plugin import getPlugin
from girder.utility import mail_utils
from girder.utility.model_importer import ModelImporter
from girder_jobs.models.job import Job

from dive_utils import constants

from .client_webroot import ClientWebroot
from .crud_annotation import GroupItem, RevisionLogItem, TrackItem
from .event import DIVES3Imports, process_fs_import, process_s3_import, send_new_user_email
from .views_annotation import AnnotationResource
from .views_configuration import ConfigurationResource
from .views_dataset import DatasetResource
from .views_override import countJobs, use_private_queue, list_shared_folders, get_root_path_or_relative
from .views_rpc import RpcResource


class GirderPlugin(plugin.GirderPlugin):
    def load(self, info):
        
        def setRequestAccess(self, doc, user, level, save=False, flags=None, currentUser=None,
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
        Folder.setRequestAccess = setRequestAccess

        Collection().createCollection(name='Shared Data', description='Collection containing shared datasets', reuseExisting=True)
        
        ModelImporter.registerModel('trackItem', TrackItem, plugin='dive_server')
        ModelImporter.registerModel('groupItem', GroupItem, plugin='dive_server')
        ModelImporter.registerModel('revisionLogItem', RevisionLogItem, plugin='dive_server')

        info["apiRoot"].dive_annotation = AnnotationResource("dive_annotation")
        info["apiRoot"].dive_configuration = ConfigurationResource("dive_configuration")
        info["apiRoot"].dive_dataset = DatasetResource("dive_dataset")
        info["apiRoot"].dive_rpc = RpcResource("dive_rpc")
        # required because girder doesn't load plugins in order so we need to manually load first.
        getPlugin('jobs').load(info)
        # Setup route additions for exsting resources
        info['apiRoot'].job.route("GET", ("queued",), countJobs)
        info["apiRoot"].user.route("PUT", (":id", "use_private_queue"), use_private_queue)
        info["apiRoot"].folder.route("GET", ("shared-folders",), list_shared_folders)
        info["apiRoot"].folder.route("GET", (":id", "rootpath_or_relative"), get_root_path_or_relative)
        User().exposeFields(AccessType.READ, constants.UserPrivateQueueEnabledMarker)

        # Expose Job dataset assocation
        Job().exposeFields(AccessType.READ, constants.JOBCONST_DATASET_ID)

        DIVE_MAIL_TEMPLATES = Path(os.path.realpath(__file__)).parent / 'mail_templates'
        mail_utils.addTemplateDirectory(str(DIVE_MAIL_TEMPLATES))

        # Relocate Girder
        info["serverRoot"], info["serverRoot"].girder = (
            ClientWebroot(),
            info["serverRoot"],
        )
        info["serverRoot"].api = info["serverRoot"].girder.api

        diveS3Import = DIVES3Imports()
        events.bind(
            "rest.post.assetstore/:id/import.before",
            "process_s3_import_before",
            diveS3Import.process_s3_import_before,
        )

        events.bind(
            "rest.post.assetstore/:id/import.after",
            "process_s3_import_after",
            diveS3Import.process_s3_import_after,
        )
        events.bind(
            "filesystem_assetstore_imported",
            "process_fs_import",
            process_fs_import,
        )
        events.bind(
            "s3_assetstore_imported",
            "process_s3_import",
            process_s3_import,
        )
        events.bind(
            'model.user.save.created',
            'send_new_user_email',
            send_new_user_email,
        )

        # Create dependency on worker
        plugin.getPlugin('worker').load(info)
        Setting().set(
            'worker.api_url',
            os.environ.get('WORKER_API_URL', 'http://girder:8080/api/v1'),
        )

        broker_url = os.environ.get('CELERY_BROKER_URL', None)
        if broker_url is None:
            raise RuntimeError('CELERY_BROKER_URL must be set')
        Setting().set('worker.broker', broker_url)
