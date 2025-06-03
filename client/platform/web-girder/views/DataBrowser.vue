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
  useStore, LocationType, isGirderModel,
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
      return isAnnotationFolder(item) && !item.public;
    }

    function isUserOwner(item: GirderModel) {
      if (item._modelType === 'folder') {
        return item.creatorId === girderRest.user._id || girderRest.user.admin;
      }
      if (item._modelType === 'user') {
        return item._id === girderRest.user._id || girderRest.user.admin;
      }
      return girderRest.user.admin;
    }

    function toggleShare(item: GirderModel) {
      shareData(item._id, !item.meta.sharableMediaId).then(() => {
        eventBus.$emit('refresh-data-browser');
      });
    }

    const shouldShowUpload = computed(() => (
      locationStore.location
      && !getters['Location/locationIsViameFolder']
      && getLocationType(locationStore.location) === 'folder'
      && !locationStore.selected.length
      && isGirderModel(locationStore.location)
      && isUserOwner(locationStore.location)
    ));

    const shouldShowNewFolder = computed(() => (
      locationStore.location
      && !getters['Location/locationIsViameFolder']
      && !locationStore.selected.length
      && isGirderModel(locationStore.location)
      && isUserOwner(locationStore.location)
    ));

    const shouldShowSelect = computed(() => (
      locationStore.location
      && !getters['Location/locationIsViameFolder']
      && isGirderModel(locationStore.location)
      && isUserOwner(locationStore.location)
    ));

    eventBus.$on('refresh-data-browser', handleNotification);
    onBeforeUnmount(() => {
      eventBus.$off('refresh-data-browser', handleNotification);
    });

    return {
      fileManager,
      locationStore,
      getters,
      toggleShare,
      shouldShowUpload,
      shouldShowNewFolder,
      shouldShowSelect,
      uploaderDialog,
      uploading,
      clientSettings,
      itemsPerPageOptions,
      /* methods */
      isAnnotationFolder,
      isUserOwner,
      canFolderBeShared,
      handleNotification,
      setLocation,
      updateUploading,
    };
  },
});
</script>

<template>
  <DiveGirderBrowser
    ref="fileManager"
    v-model="locationStore.selected"
    :selectable="shouldShowSelect"
    :new-folder-enabled="shouldShowNewFolder"
    :location="locationStore.location"
    :items-per-page.sync="clientSettings.rowsPerPage"
    :items-per-page-options="itemsPerPageOptions"
    @update:location="setLocation($event)"
  >
    <template #headerwidget>
      <v-dialog
        v-if="shouldShowUpload"
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
        v-if="isAnnotationFolder(item) && (isUserOwner(item) || item.public)"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :to="{ name: 'viewer', params: { id: item._id } }"
      >
        Launch Annotator
      </v-btn>
      <v-btn
        v-if="canFolderBeShared(item) && isUserOwner(item)"
        class="ml-2"
        x-small
        color="primary"
        depressed
        :rounded="!!item.meta.sharableMediaId"
        :outlined="!!item.meta.sharableMediaId"
        @click.stop="toggleShare(item)"
      >
        {{ !item.meta.sharableMediaId ? 'Share' : 'Unshare' }}
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
