<script lang="ts">
import {
  computed, defineComponent, ref, onBeforeUnmount,
} from 'vue';
import {
  getLocationType, GirderModel,
} from '@girder/components/src';
import { itemsPerPageOptions } from 'dive-common/constants';
import { clientSettings } from 'dive-common/store/settings';
import { useGirderRest } from 'platform/web-girder/plugins/girder';
import { shareData } from 'platform/web-girder/api';
import {
  useStore, LocationType, isGirderModel, Access,
} from '../store/types';
import Upload from './Upload.vue';
import eventBus from '../eventBus';

import DiveGirderBrowser from './DiveGirderBrowser.vue';

export default defineComponent({
  components: {
    DiveGirderBrowser,
    Upload,
  },
  setup() {
    const girderRest = useGirderRest();
    const fileManager = ref();
    const shareLoading = ref(false);
    const store = useStore();
    const uploading = ref(false);
    const uploaderDialog = ref(false);
    const locationStore = store.state.Location;
    const { getters } = store;

    function setLocation(location: LocationType) {
      store.dispatch('Location/setRouteFromLocation', location);
    }

    function handleNotification() {
      fileManager.value.$refs.girderBrowser.refresh();
    }

    function updateUploading(newval: boolean) {
      uploading.value = newval;
      if (!newval) {
        fileManager.value.$refs.girderBrowser.refresh();
        uploaderDialog.value = false;
      }
    }

    function isAnnotationFolder(item: GirderModel) {
      return item._modelType === 'folder' && item.meta.annotate;
    }

    function canFolderBeShared(item: GirderModel) {
      return isAnnotationFolder(item) && !(item.public || item.foreign_media_id || item.published);
    }

    function hasUserAccess(item: GirderModel, requiredLevel: number) {
      if (!item?.access || !girderRest.user) return false;

      if (girderRest.user.admin) return true;

      if (requiredLevel === 0 && item.public) return true;

      const userGroups = girderRest.user.groups || [];
      const userAccess = item.access.users?.find(
        (u: Access) => (u.id === girderRest.user._id && u.level >= requiredLevel),
      );
      if (userAccess) return true;

      const groupAccess = item.access.groups?.find(
        (g: Access) => (userGroups.includes(g.id) && g.level >= requiredLevel),
      );
      if (groupAccess) return true;

      return false;
    }

    function toggleShare(item: GirderModel) {
      shareLoading.value = true;
      shareData(item._id, !item.sharableMediaId)
        .then(() => {
          eventBus.$emit('refresh-data-browser');
        })
        .finally(() => {
          shareLoading.value = false;
        });
    }

    const canAddNewFolder = computed(() => (
      locationStore.location
      && !getters['Location/locationIsViameFolder']
      && !locationStore.selected.length
      && isGirderModel(locationStore.location)
      && hasUserAccess(locationStore.location, 1)
    ));

    const canUpload = computed(() => (
      locationStore.location
      && canAddNewFolder.value
      && getLocationType(locationStore.location) === 'folder'
    ));

    eventBus.$on('refresh-data-browser', handleNotification);
    onBeforeUnmount(() => {
      eventBus.$off('refresh-data-browser', handleNotification);
    });

    return {
      fileManager,
      locationStore,
      getters,
      canAddNewFolder,
      canUpload,
      shareLoading,
      uploaderDialog,
      uploading,
      clientSettings,
      itemsPerPageOptions,
      /* methods */
      isAnnotationFolder,
      canFolderBeShared,
      handleNotification,
      hasUserAccess,
      setLocation,
      toggleShare,
      updateUploading,
    };
  },
});
</script>

<template>
  <DiveGirderBrowser
    ref="fileManager"
    v-model="locationStore.selected"
    :selectable="!getters['Location/locationIsViameFolder']"
    :new-folder-enabled="canAddNewFolder"
    :location="locationStore.location"
    :items-per-page.sync="clientSettings.rowsPerPage"
    :items-per-page-options="itemsPerPageOptions"
    @update:location="setLocation($event)"
  >
    <template #headerwidget>
      <v-dialog
        v-if="canUpload"
        v-model="uploaderDialog"
        max-width="800px"
        :persistent="uploading"
      >
        <template #activator="{ on }">
          <v-btn
            class="ma-0"
            text
            small
            v-on="on"
          >
            <v-icon
              left
              color="accent"
            >
              mdi-file-upload
            </v-icon>
            Upload
          </v-btn>
        </template>
        <Upload
          :location="locationStore.location"
          @update:uploading="updateUploading"
          @close="uploaderDialog = false"
        />
      </v-dialog>
    </template>
    <template #row="{ item }">
      <span>{{ item.name }}</span>
      <v-icon
        v-if="getters['Jobs/datasetRunningState'](item._id)"
        color="warning"
        class="rotate"
      >
        mdi-autorenew
      </v-icon>
      <v-btn
        v-if="isAnnotationFolder(item) && hasUserAccess(item, 0)"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :to="{ name: 'viewer', params: { id: item._id } }"
      >
        Launch Annotator
      </v-btn>
      <v-btn
        v-if="canFolderBeShared(item) && hasUserAccess(item, 2)"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :icon="shareLoading"
        :disabled="shareLoading"
        :rounded="!shareLoading && !!item.sharableMediaId"
        :outlined="!shareLoading && !!item.sharableMediaId"
        :loading="shareLoading"
        @click.stop="toggleShare(item)"
      >
        {{ !item.sharableMediaId ? 'Share' : 'Unshare' }}
      </v-btn>
      <v-chip
        v-if="(item.foreign_media_id)"
        color="white"
        x-small
        outlined
        disabled
        class="my-0 mx-3"
      >
        cloned
      </v-chip>
      <v-chip
        v-if="(item.meta && item.meta.published)"
        color="green"
        x-small
        outlined
        disabled
        class="my-0 mx-3"
      >
        published
      </v-chip>
    </template>
  </DiveGirderBrowser>
</template>
